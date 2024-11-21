from typing import Optional
from config.logging import get_logger
import json
from utils.redis_manager import RedisManager

class QueueManager:
    def __init__(self, redis_manager:RedisManager):
        if not hasattr(self, 'initialized'):
            self.redis_client = redis_manager.redis_client
            self.logger = get_logger(__name__)
            self.initialized = True

    def get_queue_key(self, user_id: str) -> str:
        return f"queue:{user_id}"

    async def put(self, user_id: str, message: dict):
        queue_key = self.get_queue_key(user_id)
        await self.redis_client.lpush(queue_key, json.dumps(message))

    async def get(self, user_id: str, timeout: int = 1) -> Optional[dict]:
        queue_key = self.get_queue_key(user_id)
        result = await self.redis_client.brpop(queue_key, timeout=timeout)
        if result:
            return json.loads(result[1])
        return None

    async def clear_user_queue(self, user_id: str):
        queue_key = self.get_queue_key(user_id)
        await self.redis_client.delete(queue_key)
        self.logger.info(f"Cleared queue for user: {user_id}")