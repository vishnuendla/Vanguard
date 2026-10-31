from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

IncidentStatus = Literal["new", "reviewed", "relevant", "dismissed"]
Severity = Literal["critical", "high", "moderate", "low"]
Criticality = Literal["critical", "high", "medium", "low"]


class StatusUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: IncidentStatus
    rationale: Annotated[str, Field(min_length=3, max_length=500)]


class Evidence(BaseModel):
    id: str
    title: str
    source: str
    source_url: str
    published_at: str
    summary: str
    signal_type: str

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("source_url must use http or https")
        return value


class Vendor(BaseModel):
    id: str
    name: str
    category: str
    criticality: Criticality
    locations: list[str]
    open_orders: int
    estimated_exposure_usd: int
    approved_alternatives: list[str]


class Incident(BaseModel):
    id: str
    vendor_id: str
    vendor_name: str
    vendor_category: str
    title: str
    summary: str
    event_type: str
    severity: Severity
    confidence: int
    risk_score: int
    open_orders: int
    open_order_exposure_usd: int
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
    old_status: IncidentStatus
    new_status: IncidentStatus
    rationale: str
    created_at: str


class StatusUpdateResponse(BaseModel):
    incident: str
    status: IncidentStatus
    audit_event: AuditEvent


class HealthResponse(BaseModel):
    status: str
    service: str


class PublicConfig(BaseModel):
    demo_token: str
