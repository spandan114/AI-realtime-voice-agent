import re
import time
import queue
import threading
import os
import wave
from pathlib import Path
# from playsound import playsound
import sounddevice as sd
import soundfile as sf
from openai import OpenAI
from deepgram import DeepgramClient, SpeakWebSocketEvents, SpeakWSOptions
from colorama import Fore
from abc import ABC, abstractmethod
from typing import List, Optional

class BaseTTSProvider(ABC):
    """Abstract base class for TTS providers"""
    
    @abstractmethod
    def generate_audio(self, text: str, output_path: str) -> Optional[str]:
        """Generate audio from text and save to file"""
        pass

class OpenAITTSProvider(BaseTTSProvider):
    """OpenAI TTS Provider"""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.voice = "alloy"
        self.speed = 1.1
        
    def set_voice(self, voice: str):
        if voice in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]:
            self.voice = voice
    
    def generate_audio(self, text: str, output_path: str) -> Optional[str]:
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=self.voice,
                input=text,
                speed=self.speed
            )
            
            response.stream_to_file(output_path)
            print(f"{Fore.GREEN}Generated audio file: {output_path}{Fore.RESET}")
            return output_path
            
        except Exception as e:
            print(f"{Fore.RED}OpenAI TTS Error: {str(e)}{Fore.RESET}")
            return None

class DeepgramTTSProvider(BaseTTSProvider):
    """Deepgram TTS Provider"""
    
    def __init__(self, api_key: str):
        self.client = DeepgramClient(api_key)
        self.model = "aura-asteria-en"
        self.sample_rate = 16000
        
    def set_model(self, model: str):
        self.model = model
        
    def _create_wav_header(self, output_path: str):
        """Create a WAV header for the output file"""
        with wave.open(output_path, "wb") as header:
            header.setnchannels(1)  # Mono audio
            header.setsampwidth(2)  # 16-bit audio
            header.setframerate(self.sample_rate)
            header.writeframes(b'')  # Write empty frames to initialize the file
        
    def generate_audio(self, text: str, output_path: str) -> Optional[str]:
        try:
            print(f"{Fore.CYAN}Initializing Deepgram TTS for: {text}{Fore.RESET}")
            
            # Create a wav file first (Deepgram outputs wav)
            wav_path = output_path.replace('.mp3', '.wav')
            self._create_wav_header(wav_path)
            
            # Event to track when audio generation is complete
            audio_complete = threading.Event()
            audio_failed = threading.Event()
            
            # Create a websocket connection
            dg_connection = self.client.speak.websocket.v("1")

            class WebSocketCallbacks:
                def __init__(self, wav_path, audio_complete, audio_failed):
                    self.wav_path = wav_path
                    self.audio_complete = audio_complete
                    self.audio_failed = audio_failed

                def on_open(self, client, data):
                    print(f"{Fore.GREEN}Deepgram WebSocket connected{Fore.RESET}")
                
                def on_error(self, client, error):
                    print(f"{Fore.RED}Deepgram WebSocket error: {error}{Fore.RESET}")
                    self.audio_failed.set()
                
                def on_close(self, client, data):
                    print(f"{Fore.YELLOW}Deepgram WebSocket closed{Fore.RESET}")
                    self.audio_complete.set()
                
                def on_binary_data(self, client, data):
                    try:
                        with open(self.wav_path, "ab") as f:
                            f.write(data)
                            f.flush()
                    except Exception as e:
                        print(f"{Fore.RED}Error writing audio data: {str(e)}{Fore.RESET}")
                        self.audio_failed.set()
            
            # Initialize callbacks
            callbacks = WebSocketCallbacks(wav_path, audio_complete, audio_failed)
            
            # Register event handlers
            dg_connection.on(SpeakWebSocketEvents.Open, callbacks.on_open)
            dg_connection.on(SpeakWebSocketEvents.Error, callbacks.on_error)
            dg_connection.on(SpeakWebSocketEvents.Close, callbacks.on_close)
            dg_connection.on(SpeakWebSocketEvents.AudioData, callbacks.on_binary_data)
            
            # Set up connection options
            options = SpeakWSOptions(
                model=self.model,
                encoding="linear16",
                sample_rate=self.sample_rate
            )
            
            # Start connection
            if not dg_connection.start(options):
                print(f"{Fore.RED}Failed to start Deepgram connection{Fore.RESET}")
                return None
            
            # Send text and wait for processing
            dg_connection.send_text(text)
            dg_connection.flush()
            
            # Wait for audio generation to complete or timeout
            timeout = len(text) * 0.2 + 2.0  # Adjust timeout based on text length
            audio_complete.wait(timeout=timeout)
            
            if audio_failed.is_set():
                print(f"{Fore.RED}Audio generation failed{Fore.RESET}")
                dg_connection.finish()
                return None
            
            # Close connection
            dg_connection.finish()
            
            if os.path.exists(wav_path) and os.path.getsize(wav_path) > 44:  # Check if file exists and has content beyond header
                print(f"{Fore.GREEN}Generated audio file: {wav_path}{Fore.RESET}")
                return wav_path
            else:
                print(f"{Fore.RED}No audio data was generated{Fore.RESET}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}Deepgram TTS Error: {str(e)}{Fore.RESET}")
            return None

class TextToSpeechHandler:
    """Main TTS handler supporting multiple providers"""
    
    def __init__(self, provider_name: str = "openai", **kwargs):
        self.provider = self._setup_provider(provider_name, **kwargs)
        
        # Create queues and events
        self.sentence_queue = queue.Queue()
        self.audio_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.is_playing = threading.Event()
        
        # Create audio directory in current working directory
        self.audio_dir = Path.cwd() / "audio_files"
        self.audio_dir.mkdir(exist_ok=True)
        print(f"{Fore.CYAN}Audio directory created at: {self.audio_dir}{Fore.RESET}")
        
        # Start worker threads
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.playback_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self.tts_thread.start()
        self.playback_thread.start()

    def _setup_provider(self, provider_name: str, **kwargs) -> BaseTTSProvider:
        providers = {
            "openai": OpenAITTSProvider,
            "deepgram": DeepgramTTSProvider
        }
        
        if provider_name not in providers:
            raise ValueError(f"Unsupported provider: {provider_name}")
        
        api_key = kwargs.get('api_key') or os.getenv(f"{provider_name.upper()}_API_KEY")
        if not api_key:
            raise ValueError(f"Missing API key for {provider_name}")
        
        provider = providers[provider_name](api_key)
        
        # Configure provider-specific settings
        if provider_name == "openai" and "voice" in kwargs:
            provider.set_voice(kwargs['voice'])
        elif provider_name == "deepgram" and "model" in kwargs:
            provider.set_model(kwargs['model'])
            
        return provider

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences for processing"""
        text = ' '.join(text.split())
        sentences = re.split(r'(?<!\b\w\.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences

    def _generate_audio(self, text: str) -> Optional[str]:
        """Generate audio using configured provider"""
        try:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            file_count = len(list(self.audio_dir.glob("*.*")))  # Count all audio files
            
            # Use appropriate extension based on provider
            extension = ".wav" if isinstance(self.provider, DeepgramTTSProvider) else ".mp3"
            filename = f"speech_{timestamp}_{file_count}{extension}"
            output_path = self.audio_dir / filename
            
            print(f"{Fore.CYAN}Generating audio file: {output_path}{Fore.RESET}")
            return self.provider.generate_audio(text, str(output_path))
        except Exception as e:
            print(f"{Fore.RED}Error generating audio: {str(e)}{Fore.RESET}")
            return None

    def _tts_worker(self):
        """Worker thread for TTS processing"""
        while not self.stop_event.is_set():
            try:
                sentence = self.sentence_queue.get(timeout=1)
                print(f"{Fore.CYAN}Processing sentence: {sentence}{Fore.RESET}")
                audio_file = self._generate_audio(sentence)
                
                if audio_file:
                    self.audio_queue.put(audio_file)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"{Fore.RED}Error in TTS worker: {str(e)}{Fore.RESET}")

    def _play_audio(self, audio_file: str):
        """Play a single audio file using sounddevice"""
        try:
            print(f"{Fore.GREEN}Playing audio file: {audio_file}{Fore.RESET}")
            self.is_playing.set()
            
            # Load the audio file
            data, samplerate = sf.read(audio_file)
            
            # Play the audio
            sd.play(data, samplerate)
            sd.wait()  # Wait until the audio is finished playing
            
        except Exception as e:
            print(f"{Fore.RED}Error playing audio: {str(e)}{Fore.RESET}")
        finally:
            self.is_playing.clear()

    def _playback_worker(self):
        """Worker thread for audio playback"""
        while not self.stop_event.is_set():
            try:
                audio_file = self.audio_queue.get(timeout=1)
                self._play_audio(audio_file)
                
                # Delete after playing
                try:
                    os.remove(audio_file)
                    print(f"{Fore.YELLOW}Deleted audio file: {audio_file}{Fore.RESET}")
                except Exception as e:
                    print(f"{Fore.RED}Error deleting file {audio_file}: {str(e)}{Fore.RESET}")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"{Fore.RED}Error in playback worker: {str(e)}{Fore.RESET}")

    def speak(self, text: str):
        """Public method to process and speak text"""
        sentences = self._split_into_sentences(text)
        for sentence in sentences:
            self.sentence_queue.put(sentence)

    def stop(self):
        """Stop TTS and playback"""
        self.stop_event.set()
        
        # Clean up audio files
        for file in self.audio_dir.glob("*.*"):  # Clean up both .mp3 and .wav files
            try:
                os.remove(file)
                print(f"{Fore.YELLOW}Cleanup: Deleted {file}{Fore.RESET}")
            except Exception as e:
                print(f"{Fore.RED}Error deleting {file}: {str(e)}{Fore.RESET}")
                
        # Remove audio directory if empty
        try:
            if not any(self.audio_dir.iterdir()):
                self.audio_dir.rmdir()
                print(f"{Fore.YELLOW}Removed empty audio directory: {self.audio_dir}{Fore.RESET}")
        except Exception as e:
            print(f"{Fore.RED}Error removing audio directory: {str(e)}{Fore.RESET}")