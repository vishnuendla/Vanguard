from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import engine


def test_incidents_are_sorted_by_risk_then_recency() -> None:
    incidents = engine.load_incidents()
    keys = [(incident.risk_score, incident.last_updated) for incident in incidents]
    assert keys == sorted(keys, reverse=True)


def test_scores_are_bounded_and_severity_matches_risk() -> None:
    for incident in engine.load_incidents():
        assert 0 <= incident.risk_score <= 99
        assert 0 <= incident.confidence <= 100
        assert incident.severity in {"critical", "high", "moderate", "low"}


def test_duplicate_signal_records_remain_distinct_evidence() -> None:
    northstar = next(
        incident
        for incident in engine.load_incidents()
        if incident.vendor_id == "northstar-logistics"
    )
    assert len(northstar.evidence) == 2
    assert {item.id for item in northstar.evidence} == {"sig-1001", "sig-1002"}


def test_incident_separates_confirmed_evidence_from_inference() -> None:
    incidents = {item.vendor_id: item for item in engine.load_incidents()}

    northstar = incidents["northstar-logistics"]
    assert northstar.facts == [item.summary for item in northstar.evidence]
    assert any(
        "exposure context, not confirmed loss" in item for item in northstar.inferred_impacts
    )
    assert any("Approved alternatives on file" in item for item in northstar.inferred_impacts)
    assert engine.ORDER_VERIFICATION in northstar.verification_needed
    assert any("carrier routing" in item for item in northstar.verification_needed)

    solstice = incidents["solstice-energy"]
    assert any("No approved alternative" in item for item in solstice.inferred_impacts)


def test_vendors_are_typed_and_carry_criticality() -> None:
    vendors = engine.load_vendors()
    assert len(vendors) == 4
    assert {vendor.criticality for vendor in vendors} == {"critical", "high", "medium"}
    assert all(vendor.open_orders >= 0 for vendor in vendors)


def test_signals_for_unknown_vendors_are_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "vendors.json").write_text(
        json.dumps(
            [
                {
                    "id": "known",
                    "name": "Known Vendor",
                    "category": "Test",
                    "criticality": "high",
                    "locations": ["Test City"],
                    "open_orders": 1,
                    "estimated_exposure_usd": 1000,
                    "approved_alternatives": [],
                },
                {
                    "id": "quiet",
                    "name": "No Signal Vendor",
                    "category": "Test",
                    "criticality": "low",
                    "locations": ["Quiet City"],
                    "open_orders": 0,
                    "estimated_exposure_usd": 0,
                    "approved_alternatives": [],
                },
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "signals.json").write_text(
        json.dumps(
            [
                {
                    "id": "sig-known",
                    "vendor_id": "known",
                    "title": "Known signal",
                    "source": "Test",
                    "source_url": "https://example.com/known",
                    "published_at": "2026-10-31T00:00:00Z",
                    "summary": "Known summary.",
                    "signal_type": "shipment delay",
                    "locations": ["Test City"],
                    "severity_weight": 50,
                    "confidence": 80,
                },
                {
                    "id": "sig-unknown",
                    "vendor_id": "unknown",
                    "title": "Unknown signal",
                    "source": "Test",
                    "source_url": "https://example.com/unknown",
                    "published_at": "2026-10-31T00:00:00Z",
                    "summary": "Unknown summary.",
                    "signal_type": "shipment delay",
                    "locations": ["Elsewhere"],
                    "severity_weight": 90,
                    "confidence": 90,
                },
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(engine, "DATA_DIR", tmp_path)

    incidents = engine.load_incidents()

    assert [incident.vendor_id for incident in incidents] == ["known"]
    assert {item.id for item in incidents[0].evidence} == {"sig-known"}
