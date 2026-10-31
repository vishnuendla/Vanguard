from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> str:
    """Return the current UTC time as a second-precision ISO-8601 string."""
    return datetime.now(UTC).isoformat(timespec="seconds")
