from fastapi import APIRouter
from fastapi.websockets import WebSocket, WebSocketDisconnect
from services.websocket_manager import ConnectionManager
from config.logging import get_logger
from config.settings import Settings
# from utils.save_audio import AudioSaver
from core.audio_transcriber import AudioTranscriber
from core.stream_manager import AudioStreamManager
from utils.silence_detector import WebRTCVAD
from utils.redis_manager import RedisManager 
from utils.queue_manager import QueueManager
import asyncio

logger = get_logger(__name__)
router = APIRouter()
manager = ConnectionManager()
# audio_saver = AudioSaver()
setting = Settings()
vad = WebRTCVAD(mode=3)
transcriber = AudioTranscriber(model="vosk")

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
async def audio_websocket_endpoint(websocket: WebSocket, client_id: str):

    redis_manager = RedisManager()
    queue_manager = QueueManager(redis_manager)
    stream_manager = AudioStreamManager(redis_manager, queue_manager, vad, transcriber, manager)
    await manager.connect(websocket)

    try:
        # Create tasks
        queue_task = asyncio.create_task(stream_manager.process_queue(client_id, websocket))
        audio_task = asyncio.create_task(stream_manager.process_audio(client_id, websocket))

        # Wait for tasks to complete
        await asyncio.gather(queue_task, audio_task)
    except WebSocketDisconnect:
        # Clean up tasks
        queue_task.cancel()
        audio_task.cancel()
        # Clean up connections
        await manager.disconnect(websocket)
        await queue_manager.clear_user_queue(client_id)  # Clear any pending messages
    except Exception as e:
        logger.error(f"Error in audio websocket: {e}")
    finally:
        # Clean up tasks
        queue_task.cancel()
        audio_task.cancel()
        # Clean up connections
        await manager.disconnect(websocket)
        await queue_manager.clear_user_queue(client_id)  # Clear any pending messages