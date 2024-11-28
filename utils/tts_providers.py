from abc import ABC, abstractmethod
from typing import AsyncGenerator
from openai import AsyncOpenAI
from deepgram import (
    DeepgramClient, 
    DeepgramClientOptions,
    SpeakOptions
)
from config.logging import get_logger
import asyncio
import math

logger = get_logger(__name__)

class AsyncBaseTTSProvider(ABC):
    @abstractmethod
    async def generate_audio_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        pass

class AsyncOpenAITTSProvider(AsyncBaseTTSProvider):
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.voice = "alloy"
        
    async def generate_audio_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        try:
            response = await self.client.audio.speech.create(
                model="tts-1",
                voice=self.voice,
                input=text,
            )
            
            # Get the raw bytes from the response
            audio_data = response.content

            # Optimal chunk size calculation
            # 16KB chunks - better for modern networks and browsers
            # This balances between network efficiency and playback smoothness
            CHUNK_SIZE = 16 * 1024  # 16KB
            
            # Calculate optimal sleep time based on audio duration and chunks
            total_chunks = math.ceil(len(audio_data) / CHUNK_SIZE)
            
            # Assuming 24kHz sample rate for OpenAI TTS
            # Calculate approximate audio duration (in seconds)
            audio_duration = len(audio_data) / (24000 * 2)  # 24kHz * 16bit
            
            # Calculate sleep time between chunks
            # Slightly faster than real-time to account for network latency
            sleep_time = (audio_duration / total_chunks) * 0.5
            
            for i in range(0, len(audio_data), CHUNK_SIZE):
                chunk = audio_data[i:i + CHUNK_SIZE]
                if chunk:
                    yield chunk
                    # Dynamic sleep time for smoother playback
                    await asyncio.sleep(sleep_time)
                
                    
        except Exception as e:
            print(f"Error in OpenAI TTS: {str(e)}")
            raise


class AsyncDeepgramTTSProvider:
    def __init__(self, api_key: str):
        config = DeepgramClientOptions()
        self.client = DeepgramClient(api_key, config)
        self.model = "aura-asteria-en"

    async def generate_audio_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Generate streaming audio from text using async REST API"""
        try:
            options = SpeakOptions(
                model=self.model
            )

            CHUNK_SIZE = 16 * 1024  # 16KB chunks
            current_chunk = b''
            
            response = await self.client.speak.asyncrest.v("1").stream_raw(
                {"text": text}, 
                options
            )

            async for chunk in response.aiter_bytes():
                if chunk:
                    current_chunk += chunk
                    while len(current_chunk) >= CHUNK_SIZE:
                        yield current_chunk[:CHUNK_SIZE]
                        current_chunk = current_chunk[CHUNK_SIZE:]
                        await asyncio.sleep(0.07)  # Fixed sleep time for consistent delivery

            # Send any remaining data
            if current_chunk:
                yield current_chunk

            await response.aclose()

        except Exception as e:
            logger.error(f"Error in Deepgram audio stream: {str(e)}")
            raise
