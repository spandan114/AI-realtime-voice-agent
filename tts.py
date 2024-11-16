"""
Text-to-Speech (TTS) System
==========================

This system converts text to speech using either OpenAI or Deepgram's TTS services.
It processes text in a pipeline:

Flow:
1. Input text is split into sentences to generate audio faster
2. Sentences are queued for processing
3. Audio files are generated for each sentence
4. Audio files are played in sequence
5. Files are automatically cleaned up after playback

Architecture:
------------
                Text Input
                    ↓
            Sentence Splitter
                    ↓
            [Sentence Queue] → TTS Worker → Creates audio files
                    ↓
            [Audio Queue] → Playback Worker → Plays and deletes files
"""

import re
import time
import queue
import threading
import os
from timing_utils import time_process
from pathlib import Path
import sounddevice as sd
import soundfile as sf
from openai import OpenAI
from deepgram import DeepgramClient, SpeakOptions
from colorama import Fore
from abc import ABC, abstractmethod
from typing import List, Optional

class BaseTTSProvider(ABC):
    """
    Abstract base class defining the interface for TTS providers.
    Any new TTS provider must implement the generate_audio method.
    """
    
    @abstractmethod
    def generate_audio(self, text: str, output_path: str) -> Optional[str]:
        """
        Generate audio from text and save to file.
        
        Args:
            text: Text to convert to speech
            output_path: Where to save the audio file
            
        Returns:
            Path to generated audio file or None if generation failed
        """
        pass

class OpenAITTSProvider(BaseTTSProvider):
    """
    OpenAI's Text-to-Speech implementation.
    Supports multiple voices and adjustable speech speed.
    """
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.voice = "alloy"  # Default voice
        self.speed = 1.1      # Slightly faster than normal
        
    def set_voice(self, voice: str):
        """
        Set the voice to use for TTS.
        Available voices: alloy, echo, fable, onyx, nova, shimmer
        """
        if voice in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]:
            self.voice = voice
    
    def generate_audio(self, text: str, output_path: str) -> Optional[str]:
        """Generate audio using OpenAI's TTS API"""
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
    """
    Deepgram's Text-to-Speech implementation.
    Supports multiple voice models optimized for different use cases.
    """
    
    def __init__(self, api_key: str):
        self.client = DeepgramClient(api_key)
        self.model = "aura-arcas-en"  # Default model
        
    def set_model(self, model: str):
        """
        Set the model to use for TTS.
        Available models:
        - aura-arcas-en: General purpose
        - aura-luna-en: Optimized for long-form content
        - aura-asteria-en: Optimized for natural conversation
        """
        self.model = model
        
    def generate_audio(self, text: str, output_path: str) -> Optional[str]:
        """Generate audio using Deepgram's TTS API"""
        try:
            print(f"{Fore.CYAN}Initializing Deepgram TTS for: {text}{Fore.RESET}")
            
            options = SpeakOptions(
                model=self.model,
                encoding="linear16",
                container="wav"
            )
            
            speak_options = {"text": text}
            response = self.client.speak.v("1").save(output_path, speak_options, options)
            
            # Verify file was created successfully (WAV header is 44 bytes)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 44:
                print(f"{Fore.GREEN}Generated audio file: {output_path}{Fore.RESET}")
                return output_path
            else:
                print(f"{Fore.RED}No audio data was generated{Fore.RESET}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}Deepgram TTS Error: {str(e)}{Fore.RESET}")
            return None
        
class TextToSpeechHandler:
    """
    Main TTS handler that coordinates the entire TTS pipeline:
    1. Text input → Sentence splitting
    2. Sentence queue → TTS processing
    3. Audio queue → Playback and cleanup
    """
    
    def __init__(self, provider_name: str = "openai",timer=None, **kwargs):
        self.timer = timer
        # Initialize the chosen TTS provider
        self.provider = self._setup_provider(provider_name, **kwargs)
        
        # Set up queues for the pipeline
        self.sentence_queue = queue.Queue()  # Holds sentences waiting to be converted
        self.audio_queue = queue.Queue()     # Holds audio files waiting to be played
        
        # Control flags
        self.stop_event = threading.Event()  # Signals workers to stop
        self.is_playing = threading.Event()  # Indicates if audio is currently playing
        
        # Create directory for temporary audio files
        self.audio_dir = Path.cwd() / "audio_files"
        self.audio_dir.mkdir(exist_ok=True)
        print(f"{Fore.CYAN}Audio directory created at: {self.audio_dir}{Fore.RESET}")
        
        # Start worker threads
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.playback_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self.tts_thread.start()
        self.playback_thread.start()

    def _setup_provider(self, provider_name: str, **kwargs) -> BaseTTSProvider:
        """
        Set up the requested TTS provider with appropriate configuration.
        
        Args:
            provider_name: Either 'openai' or 'deepgram'
            **kwargs: Provider-specific settings (api_key, voice, model)
            
        Returns:
            Configured TTS provider instance
        """
        providers = {
            "openai": OpenAITTSProvider,
            "deepgram": DeepgramTTSProvider
        }
        
        if provider_name not in providers:
            raise ValueError(f"Unsupported provider: {provider_name}")
        
        # Get API key from kwargs or environment variables
        api_key = kwargs.get('api_key') or os.getenv(f"{provider_name.upper()}_API_KEY")
        if not api_key:
            raise ValueError(f"Missing API key for {provider_name}")
        
        # Initialize provider
        provider = providers[provider_name](api_key)
        
        # Configure provider-specific settings
        if provider_name == "openai" and "voice" in kwargs:
            provider.set_voice(kwargs['voice'])
        elif provider_name == "deepgram" and "model" in kwargs:
            provider.set_model(kwargs['model'])
            
        return provider

    @time_process("text_splitting")
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into natural sentences for processing.
        
        Example:
            Input: "Hello! How are you today? I'm doing well."
            Output: ["Hello!", "How are you today?", "I'm doing well."]
        
        Uses regex to handle common sentence endings (., !, ?) while avoiding
        false splits on abbreviations (Mr., Dr., etc.)
        """
        text = ' '.join(text.split())  # Normalize whitespace
        sentences = re.split(r'(?<!\b\w\.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s', text)
        return [s.strip() for s in sentences if s.strip()]

    @time_process("audio_generation")
    def _generate_audio(self, text: str) -> Optional[str]:
        """
        Generate audio file for a single sentence.
        
        Creates a uniquely named audio file using timestamp and counter
        to avoid conflicts when processing multiple sentences quickly.
        """
        try:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            file_count = len(list(self.audio_dir.glob("*.*")))
            
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
        """
        Worker thread that continuously:
        1. Takes sentences from the sentence queue
        2. Converts them to audio using the TTS provider
        3. Puts the resulting audio files in the audio queue
        
        Runs until stop_event is set.
        """
        while not self.stop_event.is_set():
            try:
                # Get next sentence (timeout=1 allows checking stop_event)
                sentence = self.sentence_queue.get(timeout=1)
                print(f"{Fore.CYAN}Processing sentence: {sentence}{Fore.RESET}")
                
                # Generate audio and verify success
                audio_file = self._generate_audio(sentence)
                if audio_file and os.path.exists(audio_file):
                    self.audio_queue.put(audio_file)
                else:
                    print(f"{Fore.RED}Failed to generate audio for: {sentence}{Fore.RESET}")
                
            except queue.Empty:
                continue  # No sentences to process
            except Exception as e:
                print(f"{Fore.RED}Error in TTS worker: {str(e)}{Fore.RESET}")

    @time_process("audio_playback")
    def _play_audio(self, audio_file: str):
        """
        Play a single audio file using sounddevice.
        
        Sets is_playing flag while audio is playing to coordinate
        with other parts of the system.
        """
        try:
            if not os.path.exists(audio_file):
                print(f"{Fore.RED}Audio file not found: {audio_file}{Fore.RESET}")
                return
                
            print(f"{Fore.GREEN}Playing audio file: {audio_file}{Fore.RESET}")
            self.is_playing.set()
            
            # Small delay to ensure file is ready
            time.sleep(0.1)
            
            # Load and play audio
            data, samplerate = sf.read(audio_file)
            sd.play(data, samplerate)
            sd.wait()  # Wait for playback to finish
            
        except Exception as e:
            print(f"{Fore.RED}Error playing audio: {str(e)}{Fore.RESET}")
        finally:
            self.is_playing.clear()

    def _playback_worker(self):
        """
        Worker thread that continuously:
        1. Takes audio files from the audio queue
        2. Plays them in sequence using sounddevice
        3. Deletes the files after playing
        
        Runs until stop_event is set.
        """
        while not self.stop_event.is_set():
            try:
                # Get next audio file (timeout=1 allows checking stop_event)
                audio_file = self.audio_queue.get(timeout=1)
                self._play_audio(audio_file)
                
                # Clean up after playing
                try:
                    os.remove(audio_file)
                    print(f"{Fore.YELLOW}Deleted audio file: {audio_file}{Fore.RESET}")
                except Exception as e:
                    print(f"{Fore.RED}Error deleting file {audio_file}: {str(e)}{Fore.RESET}")
                
            except queue.Empty:
                continue  # No audio files to play
            except Exception as e:
                print(f"{Fore.RED}Error in playback worker: {str(e)}{Fore.RESET}")

    def speak(self, text: str):
        """
        Public method to process and speak text.
        
        Splits input text into sentences and queues them for processing.
        Non-blocking - returns immediately while processing continues
        in background threads.
        """
        sentences = self._split_into_sentences(text)
        for sentence in sentences:
            self.sentence_queue.put(sentence)

    def stop(self):
        """
        Stop all TTS and playback operations.
        
        1. Signals worker threads to stop
        2. Cleans up any remaining audio files
        3. Removes audio directory if empty
        """
        self.stop_event.set()
        
        # Clean up audio files
        for file in self.audio_dir.glob("*.*"):
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

    def clear_queues(self):
        """Clear all queues and stop current playback"""
        print(f"{Fore.YELLOW}Clearing TTS queues...{Fore.RESET}")
        
        # Stop current playback
        if self.is_playing.is_set():
            sd.stop()
            self.is_playing.clear()
        
        # Clear sentence queue
        while not self.sentence_queue.empty():
            try:
                self.sentence_queue.get_nowait()
            except queue.Empty:
                break
        
        # Clear audio queue and delete files
        while not self.audio_queue.empty():
            try:
                audio_file = self.audio_queue.get_nowait()
                if audio_file and os.path.exists(audio_file):
                    try:
                        os.remove(audio_file)
                        print(f"{Fore.YELLOW}Deleted queued audio file: {audio_file}{Fore.RESET}")
                    except Exception as e:
                        print(f"{Fore.RED}Error deleting audio file {audio_file}: {e}{Fore.RESET}")
            except queue.Empty:
                break

        # Clean up any remaining audio files in directory
        try:
            for file in self.audio_dir.glob("*.*"):
                try:
                    os.remove(file)
                    print(f"{Fore.YELLOW}Deleted remaining audio file: {file}{Fore.RESET}")
                except Exception as e:
                    print(f"{Fore.RED}Error deleting file {file}: {e}{Fore.RESET}")
        except Exception as e:
            print(f"{Fore.RED}Error cleaning audio directory: {e}{Fore.RESET}")