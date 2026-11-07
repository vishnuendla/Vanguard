from __future__ import annotations

from app.rate_limit import RateLimiter


def test_rate_limiter_releases_capacity_after_its_window() -> None:
    limiter = RateLimiter(limit=2, window_seconds=60)

    assert limiter.allow("client-a", now=0)
    assert limiter.allow("client-a", now=1)
    assert not limiter.allow("client-a", now=2)
    assert limiter.allow("client-a", now=60)
