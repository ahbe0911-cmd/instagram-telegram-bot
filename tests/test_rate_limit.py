import asyncio

from ig_telegram_bot.rate_limit import SlidingWindowRateLimiter


def test_rate_limiter_reports_retry_after() -> None:
    async def scenario():
        limiter = SlidingWindowRateLimiter(1)
        return await limiter.check(42), await limiter.check(42)

    first, second = asyncio.run(scenario())

    assert first.allowed is True
    assert first.retry_after_seconds == 0
    assert second.allowed is False
    assert 1 <= second.retry_after_seconds <= 60


def test_boolean_api_remains_compatible() -> None:
    async def scenario():
        limiter = SlidingWindowRateLimiter(1)
        return await limiter.allow(7), await limiter.allow(7)

    first, second = asyncio.run(scenario())

    assert first is True
    assert second is False
