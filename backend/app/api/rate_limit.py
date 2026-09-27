"""Sliding-window rate limiter for GeoSamanvay API."""
from __future__ import annotations
import threading
import time
from collections import deque
from typing import Optional

from fastapi import Request


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self._max = max_requests
        self._window = window_seconds
        self._buckets: dict[str, deque] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        now = time.time()
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = deque()
            bucket = self._buckets[key]
            cutoff = now - self._window
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self._max:
                retry_after = int(bucket[0] + self._window - now) + 1
                return False, retry_after
            bucket.append(now)
            return True, 0


_general_limiter = SlidingWindowLimiter(120, 60)
_heavy_limiter = SlidingWindowLimiter(30, 60)

_HEAVY_PATHS = {"/ingest", "/analyze", "/harmonize", "/match"}


def check_rate_limit(request: Request) -> tuple[bool, int]:
    """Returns (allowed, retry_after). Exempt: /health."""
    path = request.url.path
    if "/health" in path:
        return True, 0

    api_key = request.headers.get("X-API-Key", "")
    client_ip = request.client.host if request.client else "unknown"
    key = f"key:{api_key}:ip:{client_ip}" if api_key else f"ip:{client_ip}"

    # Heavy endpoints get stricter limits
    is_heavy = any(h in path for h in _HEAVY_PATHS)
    limiter = _heavy_limiter if is_heavy else _general_limiter
    return limiter.check(key)
