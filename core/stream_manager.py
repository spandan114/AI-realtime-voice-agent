from fastapi.websockets import WebSocket
from config.logging import get_logger
from core.response_generator import ResponseGenerator
from core.audio_transcriber import AudioTranscriber
from services.websocket_manager import ConnectionManager
from utils.silence_detector import WebRTCVAD
from utils.redis_manager import RedisManager 
from utils.queue_manager import QueueManager
import asyncio

logger = get_logger(__name__)

class AudioStreamManager:
    def __init__(self, redis_manager:RedisManager, queue_manager:QueueManager, vad:WebRTCVAD, transcriber:AudioTranscriber, manager: ConnectionManager):
        self.redis_manager = redis_manager
        self.queue_manager = queue_manager
        self.vad = vad
        self.transcriber = transcriber
        self.manager = manager

    async def process_queue(self, client_id: str, websocket: WebSocket):
        while True:
            try:
                message = await self.queue_manager.get(client_id)
                if message and message['type'] == 'sentence':
                    await websocket.send_bytes(message["content"])
            except Exception as e:
                logger.error(f"Queue error for {client_id}: {e}")
                await asyncio.sleep(0.1)

    async def process_audio(self, client_id: str, websocket: WebSocket):
        buffer = []
        last_speech_time = asyncio.get_event_loop().time()
        response_generator = ResponseGenerator(provider="groq", connection_manager=self.redis_manager)

        while True:
            try:
                audio_chunk = await self.manager.receive_audio(websocket)
                current_time = asyncio.get_event_loop().time()

                if self.vad.is_speech(audio_chunk):
                    last_speech_time = current_time
                    transcription = self.transcriber.transcribe_buffer(audio_chunk)
                    if transcription.strip():
                        buffer.append(transcription)

                if current_time - last_speech_time > 0.5 and buffer:
                    full_text = " ".join(buffer)
                    await response_generator.process_response(full_text)
                    buffer.clear()

            except Exception as e:
                logger.error(f"Audio error for {client_id}: {e}")
                break

    async def handle_client(self, client_id: str, websocket: WebSocket):
        queue_task = asyncio.create_task(self.process_queue(client_id, websocket))
        audio_task = asyncio.create_task(self.process_audio(client_id, websocket))
        
        try:
            await asyncio.gather(queue_task, audio_task)
        finally:
            queue_task.cancel()
            audio_task.cancel()

