from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.config import DATA_DIR
from app.schemas import Evidence, Incident, Severity, Vendor

SEVERITY_BY_SCORE = ((75, "critical"), (55, "high"), (35, "moderate"), (0, "low"))
SEVERITY_WEIGHT = 0.72
EXPOSURE_WEIGHT = 12
CRITICALITY_BONUS = {"critical": 15, "high": 10, "medium": 5, "low": 0}
MAX_RISK_SCORE = 99

VERIFICATION_BY_SIGNAL_TYPE = {
    "port disruption": "Confirm carrier routing and the recovery timeline for affected shipments.",
    "shipment delay": "Confirm affected purchase orders and revised receiving dates.",
    "utility advisory": "Confirm whether supplier production sites lost usable power capacity.",
    "planned maintenance": "Confirm maintenance dates do not overlap critical deliveries.",
    "contract watch": "Confirm renewal status and the decision owner with the account team.",
}
DEFAULT_VERIFICATION = "Confirm operational impact directly with the vendor account owner."
ORDER_VERIFICATION = "Validate affected purchase orders and receiving dates against the ERP."


def _read_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_vendors() -> list[Vendor]:
    """Return the monitored vendor list from the synthetic dataset."""
    return [Vendor.model_validate(row) for row in _read_json(DATA_DIR / "vendors.json")]


def _severity_for(risk_score: int) -> Severity:
    return next(label for threshold, label in SEVERITY_BY_SCORE if risk_score >= threshold)


def _verification_steps(signals: list[dict[str, Any]]) -> list[str]:
    steps = [
        VERIFICATION_BY_SIGNAL_TYPE.get(signal["signal_type"], DEFAULT_VERIFICATION)
        for signal in signals
    ]
    steps.append(ORDER_VERIFICATION)
    return list(dict.fromkeys(steps))


def load_incidents(status_by_vendor: dict[str, str] | None = None) -> list[Incident]:
    """Build one prioritized incident per vendor that has at least one source signal."""
    vendors = {row["id"]: row for row in _read_json(DATA_DIR / "vendors.json")}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in _read_json(DATA_DIR / "signals.json"):
        if signal["vendor_id"] in vendors:
            grouped[signal["vendor_id"]].append(signal)

    # Normalize exposure against the largest monitored vendor instead of a magic constant.
    max_exposure = (
        max((vendor["estimated_exposure_usd"] for vendor in vendors.values()), default=0) or 1
    )
    statuses = status_by_vendor or {}

    incidents = []
    for vendor_id, signals in grouped.items():
        vendor = vendors[vendor_id]
        signals.sort(key=lambda row: (row["published_at"], row["id"]), reverse=True)
        max_severity = max(row["severity_weight"] for row in signals)
        avg_confidence = round(sum(row["confidence"] for row in signals) / len(signals))
        exposure_factor = min(vendor["estimated_exposure_usd"] / max_exposure, 1)
        risk_score = min(
            MAX_RISK_SCORE,
            round(
                max_severity * SEVERITY_WEIGHT
                + exposure_factor * EXPOSURE_WEIGHT
                + CRITICALITY_BONUS.get(vendor["criticality"], 0)
            ),
        )
        event_types = sorted({row["signal_type"] for row in signals})
        signal_count = len(signals)

        inferred = [
            f"{vendor['open_orders']} open purchase orders may need a delivery-date check.",
            (
                f"Up to ${vendor['estimated_exposure_usd']:,} in open-order value is associated "
                "with this vendor; this is exposure context, not confirmed loss."
            ),
        ]
        if vendor["approved_alternatives"]:
            inferred.append(
                "Approved alternatives on file: " + ", ".join(vendor["approved_alternatives"]) + "."
            )
        else:
            inferred.append(
                "No approved alternative is on file; identify a qualified backup supplier."
            )

        incidents.append(
            Incident(
                id=f"inc-{vendor_id}",
                vendor_id=vendor_id,
                vendor_name=vendor["name"],
                vendor_category=vendor["category"],
                title=f"{vendor['name']}: {signals[0]['title']}",
                summary=(
                    f"{signal_count} source signal{'s' if signal_count != 1 else ''} linked to "
                    f"{vendor['name']}. The highest reported signal is "
                    f"{signals[0]['signal_type']}; operational impact requires confirmation."
                ),
                event_type=" · ".join(event_types),
                severity=_severity_for(risk_score),
                confidence=avg_confidence,
                risk_score=risk_score,
                open_orders=vendor["open_orders"],
                open_order_exposure_usd=vendor["estimated_exposure_usd"],
                status=statuses.get(vendor_id, "new"),
                first_seen=min(row["published_at"] for row in signals),
                last_updated=max(row["published_at"] for row in signals),
                affected_locations=sorted({loc for row in signals for loc in row["locations"]}),
                facts=[row["summary"] for row in signals],
                inferred_impacts=inferred,
                verification_needed=_verification_steps(signals),
                evidence=[
                    Evidence(
                        id=row["id"],
                        title=row["title"],
                        source=row["source"],
                        source_url=row["source_url"],
                        published_at=row["published_at"],
                        summary=row["summary"],
                        signal_type=row["signal_type"],
                    )
                    for row in signals
                ],
            )
        )

    return sorted(
        incidents,
        key=lambda item: (item.risk_score, item.last_updated, item.id),
        reverse=True,
    )
