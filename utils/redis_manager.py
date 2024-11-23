from typing import Dict
import redis.asyncio as redis
import logging
from threading import Event
from dataclasses import dataclass
from fastapi import WebSocket
import time

@dataclass
class ConnectionConfig:
    host: str = 'localhost'
    port: int = 6379
    retry_interval: int = 5
    max_retries: int = -1

class RedisManager:    
    """
    - Ensures only one instance of a class exists
    - Returns the same instance every time the class is instantiated
    - Creates the instance on first call using super().__new__(cls)
    - Stores instance in _instance class variable
    """
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.config = ConnectionConfig()
            self.redis_client = None
            self.active_websockets: Dict[str, WebSocket] = {}
            self.stop_event = Event()
            self._setup_logging()
            self.initialized = True

    def _setup_logging(self):
        self.logger = logging.getLogger(__name__)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    async def register_websocket(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_websockets[client_id] = websocket
        self.logger.info(f"WebSocket registered for client: {client_id}")

    async def unregister_websocket(self, client_id: str):
        if client_id in self.active_websockets:
            del self.active_websockets[client_id]
            self.logger.info(f"WebSocket unregistered for client: {client_id}")

    def connect_redis(self) -> bool:
        retries = 0
        while self.config.max_retries == -1 or retries < self.config.max_retries:
            try:
                self.redis_client = redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    decode_responses=True
                )
                self.logger.info("Redis connection established")
                return True
            except redis.ConnectionError as e:
                retries += 1
                self.logger.error(f"Redis connection attempt {retries} failed: {str(e)}")
                time.sleep(self.config.retry_interval)
        return False

    def start(self):
        if not self.connect_redis():
            raise ConnectionError("Redis connection failed")

        self.stop_event.clear()

    async def stop(self):
        self.stop_event.set()
        await self.redis_client.close()
