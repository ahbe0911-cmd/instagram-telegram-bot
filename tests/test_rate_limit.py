import asyncio

from ig_telegram_bot.rate_limit import SlidingWindowRateLimiter


def test_rate_limiter_reports_retry_after() -> None:
    limiter = SlidingWindowRateLimiter(1)

    first = asyncio.run(limiter.check(42))
    second = asyncio.run(limiter.check(42))

    assert first.allowed is True
    assert first.retry_after_seconds == 0
    assert second.allowed is False
    assert 1 <= second.retry_after_seconds <= 60


def test_boolean_api_remains_compatible() -> None:
    limiter = SlidingWindowRateLimiter(1)

    assert asyncio.run(limiter.allow(7)) is True
    assert asyncio.run(limiter.allow(7)) is False
