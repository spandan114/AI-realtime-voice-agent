from fastapi import WebSocket
from typing import List
import numpy as np

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

    async def send_audio(self, websocket: WebSocket, audio_data: bytes):
        await websocket.send_bytes(audio_data)
        
    async def receive_audio(self, websocket: WebSocket) -> np.ndarray:
        data = await websocket.receive_bytes()
        return np.frombuffer(data, dtype=np.float32)