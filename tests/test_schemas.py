from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import SourceSignal


def test_signal_rejects_unencrypted_source_urls() -> None:
    with pytest.raises(ValidationError, match="source_url must use https"):
        SourceSignal.model_validate(
            {
                "id": "sig-test",
                "vendor_id": "vendor-test",
                "title": "Test signal",
                "source": "Test source",
                "source_url": "http://example.com/test",
                "published_at": "2026-11-07T12:00:00Z",
                "summary": "A test signal.",
                "signal_type": "test",
                "locations": ["Test City"],
                "severity_weight": 50,
                "confidence": 80,
            }
        )


def test_signal_normalizes_timezone_aware_timestamps() -> None:
    signal = SourceSignal.model_validate(
        {
            "id": "sig-test",
            "vendor_id": "vendor-test",
            "title": "Test signal",
            "source": "Test source",
            "source_url": "https://example.com/test",
            "published_at": "2026-11-07T17:30:00+05:30",
            "summary": "A test signal.",
            "signal_type": "test",
            "locations": ["Test City"],
            "severity_weight": 50,
            "confidence": 80,
        }
    )

    assert signal.published_at == "2026-11-07T12:00:00Z"
