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

import os
import asyncio
from colorama import Fore
from utils.tts_providers import AsyncBaseTTSProvider, AsyncOpenAITTSProvider, AsyncDeepgramTTSProvider
from services.websocket_manager import ConnectionManager
from config.logging import get_logger
import base64
from typing import Optional
from fastapi.websockets import WebSocket

logger = get_logger(__name__)

class TextToSpeechHandler:
    def __init__(self, provider_name: str = "openai", timer=None, **kwargs):
        self.timer = timer
        self.provider = self._setup_provider(provider_name, **kwargs)
        self.websocket_manager = ConnectionManager()
        self.is_streaming = False
        self.streaming_complete = asyncio.Event()  # Add completion event
        
    def _setup_provider(self, provider_name: str, **kwargs) -> AsyncBaseTTSProvider:
        providers = {
            "openai": AsyncOpenAITTSProvider,
            "deepgram": AsyncDeepgramTTSProvider
        }
        
        if provider_name not in providers:
            raise ValueError(f"Unsupported provider: {provider_name}")
        
        api_key = kwargs.get('api_key') or os.getenv(f"{provider_name.upper()}_API_KEY")
        if not api_key:
            raise ValueError(f"Missing API key for {provider_name}")
        
        provider = providers[provider_name](api_key)
        
        if provider_name == "openai" and "voice" in kwargs:
            provider.voice = kwargs['voice']
        elif provider_name == "deepgram" and "model" in kwargs:
            provider.model = kwargs['model']
            
        return provider

    async def stream_audio(self, text: str, websocket: WebSocket) -> bool:
        """
        Stream audio chunks and return True when complete
        """
        if not text.strip():
            logger.warning("Empty text provided for streaming")
            return False

        self.is_streaming = True
        self.streaming_complete.clear()  # Reset completion event
        chunk_count = 0
        
        try:
            logger.info(f"Starting audio stream for text: {text[:50]}...")
            
            await websocket.send_json({
                "type": "audio_stream_start",
                "text": text
            })
            
            async for chunk in self.provider.generate_audio_stream(text):
                if not self.is_streaming:
                    logger.info("Streaming was stopped")
                    break
                    
                if chunk:
                    chunk_count += 1
                    base64_chunk = base64.b64encode(chunk).decode('utf-8')
                    
                    await websocket.send_json({
                        "type": "audio_chunk",
                        "data": base64_chunk,
                        "chunk_number": chunk_count
                    })
                    
                    await asyncio.sleep(0.01)
            
            if self.is_streaming:
                await websocket.send_json({
                    "type": "audio_stream_end",
                    "total_chunks": chunk_count
                })
                
                # Wait for client to confirm playback completion
                await asyncio.sleep(0.1)  # Small buffer for network latency
                logger.info(f"Successfully streamed {chunk_count} audio chunks")
                return True
                
        except Exception as e:
            logger.error(f"Error streaming audio: {str(e)}")
            await websocket.send_json({
                "type": "audio_stream_error",
                "error": str(e),
                "chunk_number": chunk_count
            })
            return False
            
        finally:
            self.is_streaming = False
            self.streaming_complete.set()  # Signal completion

        return False



    async def stop_streaming(self) -> None:
        """
        Stop the current audio stream
        """
        self.is_streaming = False
        await self.websocket_manager.broadcast({
            "type": "audio_stream_stopped"
        })

    async def process_text(self, text: str) -> None:
        """
        Process text input and stream audio to connected clients
        """
        try:
            # Stop any existing stream
            if self.is_streaming:
                await self.stop_streaming()
                await asyncio.sleep(0.1)  # Small delay to ensure cleanup
                
            await self.stream_audio(text)
            
        except Exception as e:
            logger.error(f"Error processing text: {str(e)}")
            await self.websocket_manager.broadcast({
                "type": "error",
                "error": str(e)
            })