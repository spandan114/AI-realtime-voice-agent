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
from deepgram import DeepgramClient, SpeakOptions
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
        self.model = "aura-arcas-en"  # Default model
        
    def set_model(self, model: str):
        """Set the model to use for TTS
        Available models:
        - aura-arcas-en
        - aura-luna-en
        - aura-asteria-en
        See: https://developers.deepgram.com/docs/tts-models
        """
        self.model = model
        
    def generate_audio(self, text: str, output_path: str) -> Optional[str]:
        try:
            print(f"{Fore.CYAN}Initializing Deepgram TTS for: {text}{Fore.RESET}")
            
            # Configure options for Deepgram TTS
            options = SpeakOptions(
                model=self.model,
                encoding="linear16",
                container="wav"
            )
            
            # Set up speak options with the text
            speak_options = {"text": text}
            
            # Generate and save audio
            response = self.client.speak.v("1").save(output_path, speak_options, options)
            
            # Verify the file was created successfully
            if os.path.exists(output_path) and os.path.getsize(output_path) > 44:  # WAV header is 44 bytes
                print(f"{Fore.GREEN}Generated audio file: {output_path}{Fore.RESET}")
                return output_path
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
                
                # Generate audio and wait for completion
                audio_file = self._generate_audio(sentence)
                
                if audio_file and os.path.exists(audio_file):
                    # Ensure file is completely written
                    time.sleep(0.1)  # Small delay to ensure file is ready
                    self.audio_queue.put(audio_file)
                else:
                    print(f"{Fore.RED}Failed to generate audio for: {sentence}{Fore.RESET}")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"{Fore.RED}Error in TTS worker: {str(e)}{Fore.RESET}")


    def _play_audio(self, audio_file: str):
        """Play a single audio file using sounddevice"""
        try:
            # Ensure file exists and is ready
            if not os.path.exists(audio_file):
                print(f"{Fore.RED}Audio file not found: {audio_file}{Fore.RESET}")
                return
                
            print(f"{Fore.GREEN}Playing audio file: {audio_file}{Fore.RESET}")
            self.is_playing.set()
            
            # Small delay to ensure file is ready
            time.sleep(0.1)
            
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