from fastapi.websockets import WebSocket
from config.logging import get_logger
from core.response_generator import ResponseGenerator
from core.audio_transcriber import AudioTranscriber
from core.speech_generator import TextToSpeechHandler
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
        self.tts_generator = TextToSpeechHandler(provider_name="deepgram")
        self.current_message = None

    async def process_queue(self, client_id: str, websocket: WebSocket):
        """
        Process queue messages with confirmed completion
        If no current message → get new message from queue
        If got message → process it
        If message processed → clear current_message
        If error → clear current_message
        If already has message → wait and continue loop
        """
        while True:
            try:
                # Skip getting new message if we're still processing one
                if self.current_message is None:
                    self.current_message = await self.queue_manager.get(client_id)
                    
                    if self.current_message and self.current_message['type'] == 'sentence':
                        logger.info(f"Processing message for {client_id}: {self.current_message['content'][:50]}...")
                        
                        # Stream and wait for completion
                        streaming_success = await self.tts_generator.stream_audio(
                            self.current_message['content'], 
                            websocket
                        )

                        if streaming_success:
                            logger.info(f"Successfully completed message for {client_id}")
                            self.current_message = None
                        else:
                            logger.error(f"Failed to process message for {client_id}, skipping")
                            self.current_message = None  # Skip failed message
                    else:
                        # Not a sentence message or no message
                        self.current_message = None
                        await asyncio.sleep(0.1)
                else:
                    # We have a message being processed, wait
                    await asyncio.sleep(0.1)

            except RuntimeError as e:
                if "Cannot call 'send' once a close message has been sent" in str(e):
                    logger.info(f"WebSocket closed for {client_id}")
                    break
                raise

            except Exception as e:
                logger.error(f"Queue error for {client_id}: {e}")
                self.current_message = None  # Clear message on error
                await asyncio.sleep(0.1)

    async def process_audio(self, client_id: str, websocket: WebSocket):
        buffer = []
        last_speech_time = asyncio.get_event_loop().time()
        response_generator = ResponseGenerator(provider="groq", connection_manager=self.redis_manager)
        while True:
            try:
                audio_chunk = await self.manager.receive_audio(websocket)
                current_time = asyncio.get_event_loop().time()

                if not self.vad.is_low_energy(audio_chunk, threshold=0.01) and self.vad.is_speech(audio_chunk):
                    last_speech_time = current_time
                    transcription = self.transcriber.transcribe_buffer(audio_chunk)
                    
                    if transcription.strip():
                        buffer.append(transcription)

                if current_time - last_speech_time > 1.0 and buffer:
                    full_text = " ".join(buffer)
                    await response_generator.process_response(full_text, client_id)
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

    

