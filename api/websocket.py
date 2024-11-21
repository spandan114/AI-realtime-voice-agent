from fastapi import APIRouter
from fastapi.websockets import WebSocket, WebSocketDisconnect
from services.websocket_manager import ConnectionManager
from config.logging import get_logger
from config.settings import Settings
# from utils.save_audio import AudioSaver
from core.audio_transcriber import AudioTranscriber
from core.response_generator import ResponseGenerator
from utils.silence_detector import WebRTCVAD
from utils.redis_manager import RedisManager 
import asyncio

logger = get_logger(__name__)
router = APIRouter()
manager = ConnectionManager()
# audio_saver = AudioSaver()
setting = Settings()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        data = await websocket.receive_text()
        await manager.broadcast(f"Message: {data}")
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error in text websocket: {e}")
    finally:
        await manager.disconnect(websocket)

 
@router.websocket("/ws/audio/{client_id}")
async def audio_websocket_endpoint(websocket: WebSocket):

    redis_manager = RedisManager()  # Get singleton instance
    response_generator = ResponseGenerator(provider="groq", connection_manager=redis_manager)
    

    await manager.connect(websocket)
    # Initialize WebRTC VAD
    vad = WebRTCVAD(mode=3)  # Most aggressive speech detection
    transcriber = AudioTranscriber(model="vosk")
    transcription_buffer = []
    speech_timeout = 1.0  # 2 seconds silence threshold
    last_speech_time = asyncio.get_event_loop().time()

    try:

        while True:
            # Receive audio chunk
            audio_chunk = await manager.receive_audio(websocket)

            try:
                # Detect if the chunk contains speech
                is_speech = vad.is_speech(audio_chunk)

                current_time = asyncio.get_event_loop().time()

                if is_speech:
                    # Reset the speech timer
                    last_speech_time = current_time

                    # Transcribe the audio chunk
                    transcription = transcriber.transcribe_buffer(audio_chunk)
                    logger.info(f"Transcription: {transcription}")

                    if transcription.strip():
                        transcription_buffer.append(transcription)

                # Check for speech timeout
                if current_time - last_speech_time > speech_timeout and transcription_buffer:
                    # Combine the transcription and send it to the LLM
                    full_transcription = " ".join(transcription_buffer)
                    logger.info(f"Sending to LLM: {full_transcription}")

                    # Generate LLM response (example placeholder)
                    await response_generator.process_response(full_transcription)
                    # llm_response = await generate_llm_response(full_transcription)

                    # Send response back to the client
                    await websocket.send_text("llm_response")

                    # Clear the transcription buffer
                    transcription_buffer.clear()

            except Exception as e:
                logger.error(f"Error processing audio chunk: {e}")

    except WebSocketDisconnect:
        logger.info("Client disconnected from audio websocket")
    finally:
        await manager.disconnect(websocket)
