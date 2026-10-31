from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

IncidentStatus = Literal["new", "reviewed", "relevant", "dismissed"]


class StatusUpdate(BaseModel):
    status: IncidentStatus
    rationale: str = Field(min_length=3, max_length=500)


class Evidence(BaseModel):
    id: str
    title: str
    source: str
    source_url: str
    published_at: str
    summary: str
    signal_type: str


class Incident(BaseModel):
    id: str
    vendor_id: str
    vendor_name: str
    title: str
    summary: str
    event_type: str
    severity: str
    confidence: int
    risk_score: int
    status: IncidentStatus
    first_seen: str
    last_updated: str
    affected_locations: list[str]
    facts: list[str]
    inferred_impacts: list[str]
    verification_needed: list[str]
    evidence: list[Evidence]


class AuditEvent(BaseModel):
    id: int
    incident_id: str
    actor: str
    old_status: str
    new_status: str
    rationale: str
    created_at: str
