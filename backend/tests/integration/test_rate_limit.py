from redis.asyncio import Redis

from etheria.cache.rate_limit import RateLimiter
from etheria.core.settings import Settings


async def test_fixed_window_allows_the_limit_then_blocks(settings: Settings, clean_redis: None) -> None:
    redis = Redis.from_url(settings.redis_url)
    limiter = RateLimiter(redis)
    outcomes = [await limiter.hit("t:a", limit=3, window_s=60) for _ in range(4)]
    await redis.aclose()
    assert [allowed for allowed, _ in outcomes] == [True, True, True, False]
    assert 1 <= outcomes[-1][1] <= 60


async def test_keys_are_independent(settings: Settings, clean_redis: None) -> None:
    redis = Redis.from_url(settings.redis_url)
    limiter = RateLimiter(redis)
    for _ in range(3):
        await limiter.hit("t:a", limit=3, window_s=60)
    allowed, _ = await limiter.hit("t:b", limit=3, window_s=60)
    await redis.aclose()
    assert allowed
