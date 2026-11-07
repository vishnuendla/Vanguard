from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.config import DATA_DIR
from app.schemas import (
    Evidence,
    Incident,
    RiskExplanation,
    RiskPolicy,
    Severity,
    SourceSignal,
    Vendor,
)


class DataIntegrityError(ValueError):
    """Raised when source data cannot safely produce a complete incident queue."""


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_vendors() -> list[Vendor]:
    """Return the monitored vendor list from the synthetic dataset."""
    vendors = [Vendor.model_validate(row) for row in _read_json(DATA_DIR / "vendors.json")]
    _require_unique_ids(vendors, "vendors")
    return vendors


def load_risk_policy() -> RiskPolicy:
    """Return the validated, versioned risk policy used for every incident score."""
    return RiskPolicy.model_validate(_read_json(DATA_DIR / "risk_policy.json"))


def _require_unique_ids(records: list[Vendor] | list[SourceSignal], label: str) -> None:
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for record in records:
        if record.id in seen_ids:
            duplicate_ids.add(record.id)
        else:
            seen_ids.add(record.id)
    if duplicate_ids:
        values = ", ".join(sorted(duplicate_ids))
        raise DataIntegrityError(f"Duplicate {label} IDs: {values}")


def _severity_for(risk_score: int, policy: RiskPolicy) -> Severity:
    return next(band.severity for band in policy.severity_bands if risk_score >= band.minimum_score)


def _verification_steps(signals: list[SourceSignal], policy: RiskPolicy) -> list[str]:
    steps = [
        policy.verification_by_signal_type.get(signal.signal_type, policy.default_verification)
        for signal in signals
    ]
    steps.append(policy.order_verification)
    return list(dict.fromkeys(steps))


def load_incidents(status_by_vendor: dict[str, str] | None = None) -> list[Incident]:
    """Build one prioritized incident per vendor that has at least one source signal."""
    policy = load_risk_policy()
    vendors = {vendor.id: vendor for vendor in load_vendors()}
    signals = [SourceSignal.model_validate(row) for row in _read_json(DATA_DIR / "signals.json")]
    _require_unique_ids(signals, "signal")
    unknown_vendor_ids = sorted({signal.vendor_id for signal in signals} - set(vendors))
    if unknown_vendor_ids:
        raise DataIntegrityError(
            "Signals reference unknown vendors: " + ", ".join(unknown_vendor_ids)
        )

    grouped: dict[str, list[SourceSignal]] = defaultdict(list)
    for signal in signals:
        grouped[signal.vendor_id].append(signal)

    # Normalize exposure against the largest monitored vendor instead of a magic constant.
    max_exposure = (
        max((vendor.estimated_exposure_usd for vendor in vendors.values()), default=0) or 1
    )
    statuses = status_by_vendor or {}

    incidents = []
    for vendor_id, signals in grouped.items():
        vendor = vendors[vendor_id]
        signals.sort(key=lambda row: (row.published_at, row.id), reverse=True)
        max_severity = max(signal.severity_weight for signal in signals)
        avg_confidence = round(sum(signal.confidence for signal in signals) / len(signals))
        exposure_factor = min(vendor.estimated_exposure_usd / max_exposure, 1)
        severity_points = max_severity * policy.severity_weight
        exposure_points = exposure_factor * policy.exposure_weight
        criticality_bonus = policy.criticality_bonus[vendor.criticality]
        unbounded_score = severity_points + exposure_points + criticality_bonus
        risk_score = min(
            policy.max_score,
            round(unbounded_score),
        )
        event_types = sorted({signal.signal_type for signal in signals})
        signal_count = len(signals)
        highest_severity_signal = max(
            signals,
            key=lambda signal: (signal.severity_weight, signal.published_at, signal.id),
        )

        inferred = [
            f"{vendor.open_orders} open purchase orders may need a delivery-date check.",
            (
                f"Up to ${vendor.estimated_exposure_usd:,} in open-order value is associated "
                "with this vendor; this is exposure context, not confirmed loss."
            ),
        ]
        if vendor.approved_alternatives:
            inferred.append(
                "Approved alternatives on file: " + ", ".join(vendor.approved_alternatives) + "."
            )
        else:
            inferred.append(
                "No approved alternative is on file; identify a qualified backup supplier."
            )

        incidents.append(
            Incident(
                id=f"inc-{vendor_id}",
                vendor_id=vendor_id,
                vendor_name=vendor.name,
                vendor_category=vendor.category,
                title=f"{vendor.name}: {signals[0].title}",
                summary=(
                    f"{signal_count} source signal{'s' if signal_count != 1 else ''} linked to "
                    f"{vendor.name}. The highest-severity reported signal is "
                    f"{highest_severity_signal.signal_type}; operational impact requires "
                    "confirmation."
                ),
                event_type=" · ".join(event_types),
                severity=_severity_for(risk_score, policy),
                confidence=avg_confidence,
                risk_score=risk_score,
                risk_explanation=RiskExplanation(
                    policy_version=policy.version,
                    strongest_signal_type=highest_severity_signal.signal_type,
                    strongest_signal_weight=max_severity,
                    severity_points=round(severity_points, 2),
                    exposure_ratio=round(exposure_factor, 4),
                    exposure_points=round(exposure_points, 2),
                    criticality_bonus=criticality_bonus,
                    unbounded_score=round(unbounded_score, 2),
                    score_cap_applied=unbounded_score > policy.max_score,
                ),
                open_orders=vendor.open_orders,
                open_order_exposure_usd=vendor.estimated_exposure_usd,
                status=statuses.get(vendor_id, "new"),
                first_seen=min(signal.published_at for signal in signals),
                last_updated=max(signal.published_at for signal in signals),
                affected_locations=sorted(
                    {location for signal in signals for location in signal.locations}
                ),
                facts=[signal.summary for signal in signals],
                inferred_impacts=inferred,
                verification_needed=_verification_steps(signals, policy),
                evidence=[
                    Evidence(
                        id=signal.id,
                        title=signal.title,
                        source=signal.source,
                        source_url=signal.source_url,
                        published_at=signal.published_at,
                        summary=signal.summary,
                        signal_type=signal.signal_type,
                    )
                    for signal in signals
                ],
            )
        )

    return sorted(
        incidents,
        key=lambda item: (item.risk_score, item.last_updated, item.id),
        reverse=True,
    )
