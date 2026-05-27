import orjson
from typing import Any
from loguru import logger
from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings


class RedisBus:
    """Async Redis client for pub/sub and stream-based data pipeline."""

    def __init__(self) -> None:
        self._redis: Redis | None = None

    async def connect(self) -> None:
        pool = ConnectionPool.from_url(
            settings.redis_dsn,
            max_connections=30,
            decode_responses=True,
        )
        self._redis = Redis.from_pool(pool)
        logger.info("Connected to Redis")

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.aclose()
            logger.info("Disconnected from Redis")

    @property
    def client(self) -> Redis:
        if self._redis is None:
            raise RuntimeError("Redis not initialized")
        return self._redis

    async def publish(self, channel: str, data: dict[str, Any]) -> None:
        payload = orjson.dumps(data).decode("utf-8")
        await self.client.publish(channel, payload)

    async def xadd(self, stream: str, data: dict[str, Any], maxlen: int | None = None) -> str:
        payload = {k: orjson.dumps(v).decode("utf-8") if not isinstance(v, str) else v
                   for k, v in data.items()}
        maxlen = maxlen or settings.redis_stream_maxlen
        return await self.client.xadd(stream, payload, maxlen=maxlen, approximate=True)

    async def xrange(self, stream: str, start: str = "-", end: str = "+") -> list[dict[str, Any]]:
        raw = await self.client.xrange(stream, start, end)
        return [
            {k: orjson.loads(v) if v and v[0] in ("{", "[") else v for k, v in msg[1].items()}
            for msg in raw
        ]


bus = RedisBus()
