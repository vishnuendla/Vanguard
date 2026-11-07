from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class RateLimiter:
    """A bounded in-memory sliding-window limiter for protected API requests."""

    def __init__(self, limit: int, window_seconds: int = 60, max_clients: int = 10_000) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, client: str, now: float | None = None) -> bool:
        current_time = monotonic() if now is None else now
        with self._lock:
            requests = self._requests[client]
            cutoff = current_time - self.window_seconds
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= self.limit:
                return False
            requests.append(current_time)
            self._trim_clients()
            return True

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()

    def _trim_clients(self) -> None:
        if len(self._requests) <= self.max_clients:
            return
        oldest_client = min(
            self._requests,
            key=lambda client: self._requests[client][0] if self._requests[client] else 0,
        )
        del self._requests[oldest_client]
