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
async def audio_websocket_endpoint(websocket: WebSocket, client_id: str):

    redis_manager = RedisManager()
    queue_manager = QueueManager(redis_manager)
    vad = WebRTCVAD(mode=3)
    transcriber = AudioTranscriber(model="groq", api_key=setting.GROQ_API_KEY)
    stream_manager = AudioStreamManager(redis_manager, queue_manager, vad, transcriber, manager)
    await manager.connect(websocket)

    try:
        await stream_manager.handle_client(client_id, websocket)
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error in audio websocket: {e}")
    finally:
        await manager.disconnect(websocket)