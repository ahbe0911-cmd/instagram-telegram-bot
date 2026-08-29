from __future__ import annotations

import asyncio
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


class SlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self._limit = requests_per_minute
        self._events: dict[int, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, user_id: int) -> RateLimitDecision:
        now = time.monotonic()
        cutoff = now - 60
        async with self._lock:
            events = self._events[user_id]
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= self._limit:
                retry_after = max(1, math.ceil(60 - (now - events[0])))
                return RateLimitDecision(False, retry_after)

            events.append(now)
            return RateLimitDecision(True)

    async def allow(self, user_id: int) -> bool:
        """Backward-compatible boolean API."""
        return (await self.check(user_id)).allowed
