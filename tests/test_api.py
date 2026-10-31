from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "vanguard"}


def test_incidents_require_authentication(client: TestClient) -> None:
    response = client.get("/api/incidents")
    assert response.status_code == 401


def test_invalid_token_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/incidents", headers={"Authorization": "Bearer wrong", "X-User-Id": "analyst"}
    )
    assert response.status_code == 401


def test_dashboard_returns_cited_evidence_and_uncertainty(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/incidents", headers=auth_headers)
    assert response.status_code == 200
    incidents = response.json()
    assert len(incidents) == 4
    northstar = next(item for item in incidents if item["vendor_id"] == "northstar-logistics")
    assert northstar["evidence"]
    assert northstar["evidence"][0]["source_url"].startswith("https://")
    assert any("not confirmed loss" in item.lower() for item in northstar["inferred_impacts"])
    assert northstar["verification_needed"]


def test_status_change_requires_rationale_and_creates_audit_entry(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    incident_id = "inc-northstar-logistics"
    invalid = client.patch(
        f"/api/incidents/{incident_id}/status",
        headers=auth_headers,
        json={"status": "relevant", "rationale": "x"},
    )
    assert invalid.status_code == 422

    updated = client.patch(
        f"/api/incidents/{incident_id}/status",
        headers=auth_headers,
        json={"status": "relevant", "rationale": "Two shipment updates need follow-up."},
    )
    assert updated.status_code == 200
    assert updated.json()["audit_event"]["actor"] == "test-analyst"
    assert updated.json()["audit_event"]["old_status"] == "new"

    filtered = client.get("/api/incidents?status=relevant", headers=auth_headers)
    assert [item["id"] for item in filtered.json()] == [incident_id]
    audit = client.get(f"/api/audit?incident_id={incident_id}", headers=auth_headers)
    assert len(audit.json()) == 1
    assert audit.json()[0]["rationale"] == "Two shipment updates need follow-up."


def test_unknown_incident_returns_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/incidents/inc-does-not-exist", headers=auth_headers)
    assert response.status_code == 404
