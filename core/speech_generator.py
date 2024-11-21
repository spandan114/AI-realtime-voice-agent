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

import time
import os
from pathlib import Path
from colorama import Fore
from typing import Optional
from utils.tts_providers import BaseTTSProvider, OpenAITTSProvider, DeepgramTTSProvider
from services.websocket_manager import ConnectionManager

websocket = ConnectionManager()

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
        
        # Create directory for temporary audio files
        self.audio_dir = Path.cwd() / "audio_files"
        self.audio_dir.mkdir(exist_ok=True)
        print(f"{Fore.CYAN}Audio directory created at: {self.audio_dir}{Fore.RESET}")
        

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
        
    async def process_text(self, text: str) -> None:
        """
        Process a text input and generate audio for each sentence.
        """
        await websocket.broadcast("llm_response")