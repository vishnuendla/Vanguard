from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import DATA_DIR
from app.schemas import Evidence, Incident

SEVERITY_BY_SCORE = ((75, "critical"), (55, "high"), (35, "moderate"), (0, "low"))


def _read_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_incidents(status_by_vendor: dict[str, str] | None = None) -> list[Incident]:
    vendors = {row["id"]: row for row in _read_json(DATA_DIR / "vendors.json")}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in _read_json(DATA_DIR / "signals.json"):
        if signal["vendor_id"] in vendors:
            grouped[signal["vendor_id"]].append(signal)

    incidents = []
    for vendor_id, signals in grouped.items():
        vendor = vendors[vendor_id]
        signals.sort(key=lambda row: row["published_at"], reverse=True)
        max_severity = max(row["severity_weight"] for row in signals)
        avg_confidence = round(sum(row["confidence"] for row in signals) / len(signals))
        exposure_factor = min(vendor["estimated_exposure_usd"] / 420_000, 1)
        criticality_factor = {"critical": 15, "high": 10, "medium": 5}.get(
            vendor["criticality"], 0
        )
        risk_score = min(99, round(max_severity * 0.72 + exposure_factor * 12 + criticality_factor))
        severity = next(label for threshold, label in SEVERITY_BY_SCORE if risk_score >= threshold)
        event_types = sorted({row["signal_type"] for row in signals})
        title = f"{vendor['name']}: {signals[0]['title']}"
        signal_count = len(signals)
        inferred = [
            f"{vendor['open_orders']} open orders may need a delivery-date check.",
            (
                f"Up to ${vendor['estimated_exposure_usd']:,} in open-order value is associated "
                "with this vendor; this is exposure context, not confirmed loss."
            ),
        ]
        if vendor["approved_alternatives"]:
            inferred.append(
                "Approved alternatives on file: " + ", ".join(vendor["approved_alternatives"]) + "."
            )
        incident = Incident(
            id=f"inc-{vendor_id}",
            vendor_id=vendor_id,
            vendor_name=vendor["name"],
            title=title,
            summary=(
                f"{signal_count} source signal{'s' if signal_count != 1 else ''} linked to "
                f"{vendor['name']}. The highest reported signal is {signals[0]['signal_type']}; "
                "operational impact requires confirmation."
            ),
            event_type=" · ".join(event_types),
            severity=severity,
            confidence=avg_confidence,
            risk_score=risk_score,
            open_order_exposure_usd=vendor["estimated_exposure_usd"],
            status=(status_by_vendor or {}).get(vendor_id, "new"),
            first_seen=min(row["published_at"] for row in signals),
            last_updated=max(row["published_at"] for row in signals),
            affected_locations=sorted({loc for row in signals for loc in row["locations"]}),
            facts=[row["summary"] for row in signals],
            inferred_impacts=inferred,
            verification_needed=[
                "Confirm which purchase orders and receiving dates are affected.",
                "Check directly with the vendor for a recovery timeline.",
            ],
            evidence=[
                Evidence(
                    id=row["id"], title=row["title"], source=row["source"],
                    source_url=row["source_url"], published_at=row["published_at"],
                    summary=row["summary"], signal_type=row["signal_type"],
                )
                for row in signals
            ],
        )
        incidents.append(incident)
    return sorted(incidents, key=lambda item: (item.risk_score, item.last_updated), reverse=True)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
