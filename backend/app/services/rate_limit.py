from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int
    remaining: int


class RateLimiter(Protocol):
    async def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult: ...


class RedisRateLimiter:
    """Fixed-window counter; Redis remains the authoritative distributed rate-limit store."""

    def __init__(self, redis_url: str) -> None:
        self._redis = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)

    async def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        bucket = f"codexforge:rate-limit:{key}:{int(time.time() // window_seconds)}"
        try:
            count = await self._redis.incr(bucket)
            if count == 1:
                await self._redis.expire(bucket, window_seconds)
            ttl = await self._redis.ttl(bucket)
        except RedisError as exc:
            raise ServiceUnavailableError("Rate-limit storage is temporarily unavailable.") from exc
        retry_after = max(1, ttl if ttl > 0 else window_seconds)
        return RateLimitResult(
            allowed=count <= limit,
            retry_after_seconds=retry_after,
            remaining=max(0, limit - count),
        )

    async def close(self) -> None:
        await self._redis.aclose()


class InMemoryRateLimiter:
    """Explicitly test/local-only fallback; never use this with multiple Cloud Run instances."""

    def __init__(self) -> None:
        self._counts: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.monotonic()
        async with self._lock:
            count, expires_at = self._counts.get(key, (0, now + window_seconds))
            if expires_at <= now:
                count, expires_at = 0, now + window_seconds
            count += 1
            self._counts[key] = (count, expires_at)
        return RateLimitResult(
            allowed=count <= limit,
            retry_after_seconds=max(1, int(expires_at - now)),
            remaining=max(0, limit - count),
        )


def build_rate_limiter(settings: Settings) -> RateLimiter:
    if settings.allow_in_memory_rate_limiter and settings.is_local_or_test:
        return InMemoryRateLimiter()
    return RedisRateLimiter(settings.redis_url)
