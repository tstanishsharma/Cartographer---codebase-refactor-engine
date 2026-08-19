"""
Cartographer — Redis Cache Service.

Provides:
  - init_redis() / close_redis() lifecycle hooks
  - get_redis() FastAPI dependency
  - CacheService: typed wrapper for common cache operations
  - Pub/Sub support for real-time agent state streaming
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from redis.asyncio import Redis, from_url

from app.core.config import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)
settings = get_settings()

_redis: Redis | None = None


async def init_redis(settings_obj: object | None = None) -> None:
    """Initialise the Redis connection pool. Called once in lifespan startup."""
    global _redis  # noqa: PLW0603
    cfg = settings_obj or settings
    url = getattr(cfg, "redis_url", settings.redis_url)

    _redis = await from_url(  # type: ignore[assignment]
        url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )
    # Verify connectivity
    await _redis.ping()
    logger.info("redis.connected", url=url.split("@")[-1] if url and "@" in url else url)


async def close_redis() -> None:
    """Close the Redis connection pool on shutdown."""
    global _redis  # noqa: PLW0603
    if _redis is not None:
        await _redis.aclose()
        logger.info("redis.disconnected")
        _redis = None


def get_redis_client() -> Redis:
    """Return the module-level Redis client (must call init_redis first)."""
    if _redis is None:
        raise RuntimeError("Redis not initialised. Call init_redis() first.")
    return _redis


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency that yields the Redis client."""
    yield get_redis_client()


class CacheService:
    """
    Typed wrapper around Redis for common caching patterns.

    All keys are namespaced under "cartographer:" to avoid collisions.
    """

    NAMESPACE = "cartographer"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def _key(self, *parts: str) -> str:
        return f"{self.NAMESPACE}:{':'.join(parts)}"

    async def get(self, *key_parts: str) -> str | None:
        return await self._redis.get(self._key(*key_parts))

    async def set(self, *key_parts: str, value: str, ttl: int = 3600) -> None:
        await self._redis.setex(self._key(*key_parts), ttl, value)

    async def delete(self, *key_parts: str) -> None:
        await self._redis.delete(self._key(*key_parts))

    async def exists(self, *key_parts: str) -> bool:
        return bool(await self._redis.exists(self._key(*key_parts)))

    async def publish(self, channel: str, message: str) -> None:
        """Publish a message to a Redis pub/sub channel."""
        await self._redis.publish(self._key("channel", channel), message)

    async def get_json(self, *key_parts: str) -> Any | None:
        import json

        raw = await self.get(*key_parts)
        return json.loads(raw) if raw else None

    async def set_json(self, *key_parts: str, value: Any, ttl: int = 3600) -> None:
        import json

        await self.set(*key_parts, value=json.dumps(value), ttl=ttl)

    async def increment(self, *key_parts: str) -> int:
        return await self._redis.incr(self._key(*key_parts))

    async def lpush(self, *key_parts: str, value: str) -> None:
        await self._redis.lpush(self._key(*key_parts), value)

    async def lrange(self, *key_parts: str, start: int = 0, end: int = -1) -> list[str]:
        return await self._redis.lrange(self._key(*key_parts), start, end)
