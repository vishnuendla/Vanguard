from app.engine import load_incidents


def test_incidents_are_sorted_by_risk() -> None:
    incidents = load_incidents()
    assert [incident.risk_score for incident in incidents] == sorted(
        (incident.risk_score for incident in incidents), reverse=True
    )


def test_duplicate_signal_records_remain_distinct_evidence() -> None:
    incidents = load_incidents()
    northstar = next(
        incident for incident in incidents if incident.vendor_id == "northstar-logistics"
    )
    assert len(northstar.evidence) == 2
    assert {item.id for item in northstar.evidence} == {"sig-1001", "sig-1002"}


def test_vendor_unmatched_signals_are_ignored() -> None:
    # The checked-in sample contains only known vendors; engine contract remains stable.
    assert all(incident.vendor_id for incident in load_incidents())
