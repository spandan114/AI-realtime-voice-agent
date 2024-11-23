from abc import ABC, abstractmethod
from typing import AsyncGenerator
from openai import AsyncOpenAI
from deepgram import DeepgramClient, SpeakOptions
import asyncio
import math

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


class AsyncDeepgramTTSProvider(AsyncBaseTTSProvider):
    def __init__(self, api_key: str):
        self.client = DeepgramClient(api_key)
        self.model = "aura-arcas-en"
        
    async def generate_audio_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        try:
            options = SpeakOptions(
                model=self.model,
                encoding="linear16",
                container="wav"
            )
            
            async for chunk in await self.client.speak.v("1").stream({"text": text}, options):
                if chunk:  # Only yield if there's data
                    yield chunk
                    await asyncio.sleep(0.01)  # Small delay to prevent flooding
                    
        except Exception as e:
            print(f"Error in Deepgram TTS: {str(e)}")
            raise