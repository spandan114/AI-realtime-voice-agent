from typing import Dict, Optional
import redis.asyncio as redis
import logging
from threading import Event
from dataclasses import dataclass
from fastapi import WebSocket, WebSocketDisconnect
import time
import asyncio
import traceback

@dataclass
class ConnectionConfig:
    host: str = 'localhost'
    port: int = 6379
    retry_interval: int = 5
    max_retries: int = -1
    connection_timeout: int = 30
    heartbeat_interval: int = 30

class RedisConnectionError(Exception):
    """Raised when Redis connection fails"""
    pass

class WebSocketError(Exception):
    """Raised when WebSocket operations fail"""
    pass

class RedisManager:    
    """
    Singleton Redis manager that handles Redis connections and WebSocket management.
    
    Attributes:
        config (ConnectionConfig): Redis connection configuration
        redis_client (redis.Redis): Async Redis client instance
        active_websockets (Dict[str, WebSocket]): Active WebSocket connections
        stop_event (Event): Event to signal stopping of services
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.config = ConnectionConfig()
            self.redis_client: Optional[redis.Redis] = None
            self.active_websockets: Dict[str, WebSocket] = {}
            self.stop_event = Event()
            self._setup_logging()
            self._connection_lock = asyncio.Lock()
            self.initialized = True

    def _setup_logging(self) -> None:
        """Configure logging with detailed formatting"""
        try:
            self.logger = logging.getLogger(__name__)
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        except Exception as e:
            print(f"Failed to setup logging: {str(e)}")
            raise

    async def check_redis_connection(self) -> bool:
        """Check if Redis connection is alive"""
        try:
            if self.redis_client:
                await self.redis_client.ping()
                return True
            return False
        except (redis.ConnectionError, redis.TimeoutError):
            return False
        except Exception as e:
            self.logger.error(f"Error checking Redis connection: {str(e)}")
            return False

    async def ensure_connection(self) -> None:
        """Ensure Redis connection is active, reconnect if necessary"""
        async with self._connection_lock:
            if not await self.check_redis_connection():
                self.logger.warning("Redis connection lost, attempting to reconnect...")
                if not await self.connect_redis():
                    raise RedisConnectionError("Failed to reconnect to Redis")

    async def register_websocket(self, client_id: str, websocket: WebSocket) -> None:
        """
        Register a new WebSocket connection
        
        Args:
            client_id: Unique client identifier
            websocket: WebSocket connection to register
            
        Raises:
            WebSocketError: If registration fails
        """
        try:
            await websocket.accept()
            self.active_websockets[client_id] = websocket
            self.logger.info(f"WebSocket registered for client: {client_id}")
            
            # Start heartbeat for this connection
            asyncio.create_task(self._websocket_heartbeat(client_id))
            
        except WebSocketDisconnect:
            self.logger.warning(f"WebSocket disconnected during registration: {client_id}")
            await self.unregister_websocket(client_id)
        except Exception as e:
            self.logger.error(f"Failed to register WebSocket for {client_id}: {str(e)}\n{traceback.format_exc()}")
            raise WebSocketError(f"WebSocket registration failed: {str(e)}")

    async def unregister_websocket(self, client_id: str) -> None:
        """
        Unregister a WebSocket connection
        
        Args:
            client_id: Client identifier to unregister
        """
        try:
            if client_id in self.active_websockets:
                websocket = self.active_websockets[client_id]
                try:
                    await websocket.close()
                except Exception as e:
                    self.logger.warning(f"Error closing WebSocket for {client_id}: {str(e)}")
                finally:
                    del self.active_websockets[client_id]
                    self.logger.info(f"WebSocket unregistered for client: {client_id}")
        except Exception as e:
            self.logger.error(f"Error unregistering WebSocket for {client_id}: {str(e)}")

    async def _websocket_heartbeat(self, client_id: str) -> None:
        """Maintain WebSocket connection with periodic heartbeats"""
        while client_id in self.active_websockets and not self.stop_event.is_set():
            try:
                websocket = self.active_websockets[client_id]
                await websocket.send_text("heartbeat")
                await asyncio.sleep(self.config.heartbeat_interval)
            except Exception as e:
                self.logger.warning(f"Heartbeat failed for {client_id}: {str(e)}")
                await self.unregister_websocket(client_id)
                break

    async def connect_redis(self) -> bool:
        """
        Establish Redis connection with retry mechanism
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        retries = 0
        while self.config.max_retries == -1 or retries < self.config.max_retries:
            try:
                self.redis_client = redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    decode_responses=True,
                    socket_timeout=self.config.connection_timeout,
                    retry_on_timeout=True
                )
                # Test the connection
                await self.redis_client.ping()
                self.logger.info("Redis connection established successfully")
                return True
                
            except redis.ConnectionError as e:
                retries += 1
                self.logger.error(
                    f"Redis connection attempt {retries} failed: {str(e)}\n"
                    f"Next retry in {self.config.retry_interval} seconds"
                )
                await asyncio.sleep(self.config.retry_interval)
                
            except Exception as e:
                self.logger.error(f"Unexpected error during Redis connection: {str(e)}\n{traceback.format_exc()}")
                return False
                
        self.logger.error("Max Redis connection retries reached")
        return False

    async def start(self) -> None:
        """
        Start the Redis manager
        
        Raises:
            RedisConnectionError: If Redis connection fails
        """
        try:
            self.stop_event.clear()
            if not await self.connect_redis():
                raise RedisConnectionError("Failed to establish Redis connection")
                
            # Start connection monitoring
            asyncio.create_task(self._monitor_connection())
            
        except Exception as e:
            self.logger.error(f"Error starting Redis manager: {str(e)}\n{traceback.format_exc()}")
            raise

    async def _monitor_connection(self) -> None:
        """Monitor and maintain Redis connection"""
        while not self.stop_event.is_set():
            try:
                await self.ensure_connection()
                await asyncio.sleep(self.config.heartbeat_interval)
            except Exception as e:
                self.logger.error(f"Connection monitoring error: {str(e)}")

    async def stop(self) -> None:
        """Stop the Redis manager and clean up resources"""
        try:
            self.stop_event.set()
            
            # Close all WebSocket connections
            for client_id in list(self.active_websockets.keys()):
                await self.unregister_websocket(client_id)
                
            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()
                self.redis_client = None
                
            self.logger.info("Redis manager stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping Redis manager: {str(e)}\n{traceback.format_exc()}")
            raise
