from fastapi import APIRouter
from fastapi.websockets import WebSocket
from services.websocket_manager import ConnectionManager

router = APIRouter()
manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"Message: {data}")
    except Exception:
        await manager.disconnect(websocket)


@router.websocket("/ws/audio")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            audio_array = await manager.receive_audio(websocket)
            # Process audio here
            print("Reliving audio packet")
            # await manager.send_audio(websocket, audio_array.tobytes())
    finally:
        await manager.disconnect(websocket)