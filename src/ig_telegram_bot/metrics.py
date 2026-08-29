from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    uptime_seconds: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    rate_limited_requests: int
    media_sent: int
    bytes_sent: int


class ServiceMetrics:
    """Small in-memory counters reset whenever the process restarts."""

    def __init__(self) -> None:
        self._started_at = time.monotonic()
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._rate_limited_requests = 0
        self._media_sent = 0
        self._bytes_sent = 0
        self._lock = asyncio.Lock()

    async def record_request(self) -> None:
        async with self._lock:
            self._total_requests += 1

    async def record_success(self, media_sent: int, bytes_sent: int) -> None:
        async with self._lock:
            self._successful_requests += 1
            self._media_sent += media_sent
            self._bytes_sent += bytes_sent

    async def record_failure(self) -> None:
        async with self._lock:
            self._failed_requests += 1

    async def record_rate_limited(self) -> None:
        async with self._lock:
            self._rate_limited_requests += 1

    async def snapshot(self) -> MetricsSnapshot:
        async with self._lock:
            return MetricsSnapshot(
                uptime_seconds=max(0, int(time.monotonic() - self._started_at)),
                total_requests=self._total_requests,
                successful_requests=self._successful_requests,
                failed_requests=self._failed_requests,
                rate_limited_requests=self._rate_limited_requests,
                media_sent=self._media_sent,
                bytes_sent=self._bytes_sent,
            )
