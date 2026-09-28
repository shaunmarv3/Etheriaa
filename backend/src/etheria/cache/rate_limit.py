"""Fixed-window rate limiting in Redis (spec 8.3: Redis holds cache entries and
rate-limit counters, nothing else)."""

from redis.asyncio import Redis

from etheria.core.errors import RateLimited


class RateLimiter:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def hit(self, key: str, limit: int, window_s: int) -> tuple[bool, int]:
        """Count one attempt. Returns (allowed, seconds until the window resets)."""
        counter = f"rl:{key}"
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.incr(counter)
            pipe.expire(counter, window_s, nx=True)
            pipe.ttl(counter)
            count, _, ttl = await pipe.execute()
        return count <= limit, max(int(ttl), 1)

    async def enforce(self, key: str, limit: int, window_s: int) -> None:
        allowed, retry_after = await self.hit(key, limit, window_s)
        if not allowed:
            raise RateLimited(retry_after)
