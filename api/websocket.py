from fastapi import APIRouter
from fastapi.websockets import WebSocket, WebSocketDisconnect
from services.websocket_manager import ConnectionManager
from config.logging import get_logger
from config.settings import Settings
# from utils.save_audio import AudioSaver
from core.transcriber import DeepgramTranscriber
from core.stream_manager import AudioStreamManager
from utils.redis_manager import RedisManager 
from utils.queue_manager import QueueManager
import asyncio
from typing import Optional

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
    # Get Redis manager from application state
    redis_manager = RedisManager()
    queue_manager = QueueManager(redis_manager)
    transcriber = DeepgramTranscriber(setting.DEEPGRAM_API_KEY,websocket)
    stream_manager = AudioStreamManager(redis_manager, queue_manager, transcriber, manager)
    await manager.connect(websocket)
    tasks: list[Optional[asyncio.Task]] = []
    try:

        await transcriber.initialize()
        # Create tasks
        queue_task = asyncio.create_task(stream_manager.process_queue(client_id, websocket))
        audio_task = asyncio.create_task(stream_manager.process_audio(client_id, websocket))
        tasks = [queue_task, audio_task]

        # Wait for tasks to complete
        await asyncio.gather(*tasks)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {client_id}")
        # Handle normal disconnection - clean disconnect flow
        await stream_manager.cleanup()
        await manager.disconnect(websocket)
        await queue_manager.clear_user_queue(client_id)
        # Cancel tasks after cleanup to ensure proper shutdown
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Error in audio websocket: {e}")
        # Initiate emergency cleanup
        await stream_manager.cleanup()
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        await manager.disconnect(websocket)
        await queue_manager.clear_user_queue(client_id)
        raise  # Re-raise unexpected exceptions

    finally:
        # Final cleanup for transcriber regardless of how we exit
        await transcriber.cleanup()