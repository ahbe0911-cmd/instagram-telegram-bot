from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self._limit = requests_per_minute
        self._events: dict[int, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        cutoff = now - 60
        async with self._lock:
            events = self._events[user_id]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self._limit:
                return False
            events.append(now)
            return True
