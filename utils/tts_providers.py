# import os
# from openai import OpenAI
# from deepgram import DeepgramClient, SpeakOptions
# from colorama import Fore
# from abc import ABC, abstractmethod
# from typing import Optional


# class BaseTTSProvider(ABC):
#     """
#     Abstract base class defining the interface for TTS providers.
#     Any new TTS provider must implement the generate_audio method.
#     """
    
#     @abstractmethod
#     def generate_audio(self, text: str, output_path: str) -> Optional[str]:
#         """
#         Generate audio from text and save to file.
        
#         Args:
#             text: Text to convert to speech
#             output_path: Where to save the audio file
            
#         Returns:
#             Path to generated audio file or None if generation failed
#         """
#         pass

# class OpenAITTSProvider(BaseTTSProvider):
#     """
#     OpenAI's Text-to-Speech implementation.
#     Supports multiple voices and adjustable speech speed.
#     """
    
#     def __init__(self, api_key: str):
#         self.client = OpenAI(api_key=api_key)
#         self.voice = "alloy"  # Default voice
#         self.speed = 1.1      # Slightly faster than normal
        
#     def set_voice(self, voice: str):
#         """
#         Set the voice to use for TTS.
#         Available voices: alloy, echo, fable, onyx, nova, shimmer
#         """
#         if voice in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]:
#             self.voice = voice
    
#     def generate_audio(self, text: str, output_path: str) -> Optional[str]:
#         """Generate audio using OpenAI's TTS API"""
#         try:
#             response = self.client.audio.speech.create(
#                 model="tts-1",
#                 voice=self.voice,
#                 input=text,
#                 speed=self.speed
#             )
            
#             response.stream_to_file(output_path)
#             print(f"{Fore.GREEN}Generated audio file: {output_path}{Fore.RESET}")
#             return output_path
            
#         except Exception as e:
#             print(f"{Fore.RED}OpenAI TTS Error: {str(e)}{Fore.RESET}")
#             return None

# class DeepgramTTSProvider(BaseTTSProvider):
#     """
#     Deepgram's Text-to-Speech implementation.
#     Supports multiple voice models optimized for different use cases.
#     """
    
#     def __init__(self, api_key: str):
#         self.client = DeepgramClient(api_key)
#         self.model = "aura-arcas-en"  # Default model
        
#     def set_model(self, model: str):
#         """
#         Set the model to use for TTS.
#         Available models:
#         - aura-arcas-en: General purpose
#         - aura-luna-en: Optimized for long-form content
#         - aura-asteria-en: Optimized for natural conversation
#         """
#         self.model = model
        
#     def generate_audio(self, text: str, output_path: str) -> Optional[str]:
#         """Generate audio using Deepgram's TTS API"""
#         try:
#             print(f"{Fore.CYAN}Initializing Deepgram TTS for: {text}{Fore.RESET}")
            
#             options = SpeakOptions(
#                 model=self.model,
#                 encoding="linear16",
#                 container="wav"
#             )
            
#             speak_options = {"text": text}
#             response = self.client.speak.v("1").save(output_path, speak_options, options)
            
#             # Verify file was created successfully (WAV header is 44 bytes)
#             if os.path.exists(output_path) and os.path.getsize(output_path) > 44:
#                 print(f"{Fore.GREEN}Generated audio file: {output_path}{Fore.RESET}")
#                 return output_path
#             else:
#                 print(f"{Fore.RED}No audio data was generated{Fore.RESET}")
#                 return None
                
#         except Exception as e:
#             print(f"{Fore.RED}Deepgram TTS Error: {str(e)}{Fore.RESET}")
#             return None
  

import asyncio
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
from openai import AsyncOpenAI
from deepgram import DeepgramClient, SpeakOptions

class AsyncBaseTTSProvider(ABC):
    @abstractmethod
    async def generate_audio_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        pass

class AsyncOpenAITTSProvider(AsyncBaseTTSProvider):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.voice = "alloy"
        
    async def generate_audio_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        response = await self.client.audio.speech.create(
            model="tts-1",
            voice=self.voice,
            input=text,
        )
        async for chunk in response.iter_bytes(chunk_size=1024):
            yield chunk

class AsyncDeepgramTTSProvider(AsyncBaseTTSProvider):
    def __init__(self, api_key: str):
        self.client = DeepgramClient(api_key)
        self.model = "aura-arcas-en"
        
    async def generate_audio_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        options = SpeakOptions(
            model=self.model,
            encoding="linear16",
            container="wav"
        )
        response = await self.client.speak.v("1").stream({"text": text}, options)
        async for chunk in response:
            yield chunk