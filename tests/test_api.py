from __future__ import annotations

from fastapi.testclient import TestClient

INCIDENT_ID = "inc-northstar-logistics"


def test_health_is_public_and_sets_security_headers(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "vanguard"}
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_public_config_only_exposes_the_demo_token(client: TestClient) -> None:
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json() == {"demo_token": "local-demo-token"}


def test_public_config_never_exposes_a_deployment_token(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.main.API_TOKEN", "deployment-secret-value")
    assert client.get("/api/config").json() == {"demo_token": ""}


def test_incidents_require_authentication(client: TestClient) -> None:
    response = client.get("/api/incidents")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_invalid_token_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/incidents", headers={"Authorization": "Bearer wrong", "X-User-Id": "analyst"}
    )
    assert response.status_code == 401


def test_missing_actor_is_rejected(client: TestClient) -> None:
    response = client.get("/api/incidents", headers={"Authorization": "Bearer local-demo-token"})
    assert response.status_code == 400


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
    assert northstar["vendor_category"] == "Freight and logistics"
    assert northstar["open_orders"] == 18
    assert any("not confirmed loss" in item.lower() for item in northstar["inferred_impacts"])
    assert northstar["verification_needed"]


def test_invalid_status_filter_is_rejected(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/incidents?status=bogus", headers=auth_headers)
    assert response.status_code == 422


def test_vendors_are_protected_and_typed(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/api/vendors").status_code == 401

    response = client.get("/api/vendors", headers=auth_headers)
    assert response.status_code == 200
    vendors = response.json()
    assert len(vendors) == 4
    assert {vendor["id"] for vendor in vendors} >= {"northstar-logistics", "solstice-energy"}


def test_status_change_requires_meaningful_rationale(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    for rationale in ("x", "   "):
        response = client.patch(
            f"/api/incidents/{INCIDENT_ID}/status",
            headers=auth_headers,
            json={"status": "relevant", "rationale": rationale},
        )
        assert response.status_code == 422

    invalid_status = client.patch(
        f"/api/incidents/{INCIDENT_ID}/status",
        headers=auth_headers,
        json={"status": "urgent", "rationale": "Valid review note."},
    )
    assert invalid_status.status_code == 422


def test_status_change_creates_audit_entry_and_updates_filter(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    updated = client.patch(
        f"/api/incidents/{INCIDENT_ID}/status",
        headers=auth_headers,
        json={"status": "relevant", "rationale": "Two shipment updates need follow-up."},
    )
    assert updated.status_code == 200
    assert updated.json()["audit_event"]["actor"] == "test-analyst"
    assert updated.json()["audit_event"]["old_status"] == "new"
    assert updated.json()["audit_event"]["new_status"] == "relevant"

    filtered = client.get("/api/incidents?status=relevant", headers=auth_headers)
    assert [item["id"] for item in filtered.json()] == [INCIDENT_ID]

    audit = client.get(f"/api/audit?incident_id={INCIDENT_ID}", headers=auth_headers)
    assert len(audit.json()) == 1
    assert audit.json()[0]["rationale"] == "Two shipment updates need follow-up."


def test_repeating_the_current_status_is_a_conflict(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    first = client.patch(
        f"/api/incidents/{INCIDENT_ID}/status",
        headers=auth_headers,
        json={"status": "reviewed", "rationale": "Initial review complete."},
    )
    assert first.status_code == 200

    repeated = client.patch(
        f"/api/incidents/{INCIDENT_ID}/status",
        headers=auth_headers,
        json={"status": "reviewed", "rationale": "Confirming the same status."},
    )
    assert repeated.status_code == 409

    audit = client.get(f"/api/audit?incident_id={INCIDENT_ID}", headers=auth_headers)
    assert len(audit.json()) == 1


def test_audit_history_is_newest_first_and_bounded(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    for status in ("reviewed", "relevant"):
        response = client.patch(
            f"/api/incidents/{INCIDENT_ID}/status",
            headers=auth_headers,
            json={"status": status, "rationale": f"Move to {status}."},
        )
        assert response.status_code == 200

    events = client.get(f"/api/audit?incident_id={INCIDENT_ID}", headers=auth_headers).json()
    assert [event["new_status"] for event in events] == ["relevant", "reviewed"]

    too_large = client.get("/api/audit?limit=201", headers=auth_headers)
    assert too_large.status_code == 422
    assert client.get("/api/audit?limit=1", headers=auth_headers).json()[0]["new_status"] == (
        "relevant"
    )


def test_unknown_incident_returns_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/api/incidents/inc-does-not-exist", headers=auth_headers).status_code == 404
    assert (
        client.patch(
            "/api/incidents/inc-does-not-exist/status",
            headers=auth_headers,
            json={"status": "reviewed", "rationale": "No matching incident."},
        ).status_code
        == 404
    )
