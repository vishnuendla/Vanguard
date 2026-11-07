from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
        if not value.startswith("https://"):
            raise ValueError("source_url must use https")
        return value


class SourceSignal(Evidence):
    vendor_id: str
    locations: list[str]
    severity_weight: Annotated[int, Field(ge=0, le=100)]
    confidence: Annotated[int, Field(ge=0, le=100)]

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: str) -> str:
        try:
            published_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("published_at must be an ISO 8601 timestamp") from error
        if published_at.tzinfo is None:
            raise ValueError("published_at must include a timezone")
        return published_at.astimezone(UTC).isoformat().replace("+00:00", "Z")


class Vendor(BaseModel):
    id: str
    name: str
    category: str
    criticality: Criticality
    locations: list[str]
    open_orders: Annotated[int, Field(ge=0)]
    estimated_exposure_usd: Annotated[int, Field(ge=0)]
    approved_alternatives: list[str]


class SeverityBand(BaseModel):
    minimum_score: Annotated[int, Field(ge=0)]
    severity: Severity


class RiskPolicy(BaseModel):
    version: str
    severity_weight: Annotated[float, Field(ge=0)]
    exposure_weight: Annotated[float, Field(ge=0)]
    criticality_bonus: dict[Criticality, Annotated[int, Field(ge=0)]]
    max_score: Annotated[int, Field(ge=1, le=100)]
    severity_bands: list[SeverityBand]
    verification_by_signal_type: dict[str, str]
    default_verification: str
    order_verification: str

    @model_validator(mode="after")
    def validate_scoring_rules(self) -> RiskPolicy:
        if set(self.criticality_bonus) != {"critical", "high", "medium", "low"}:
            raise ValueError("criticality_bonus must define every criticality level")
        thresholds = [band.minimum_score for band in self.severity_bands]
        if (
            not thresholds
            or thresholds[-1] != 0
            or thresholds != sorted(set(thresholds), reverse=True)
        ):
            raise ValueError("severity_bands must use unique descending thresholds ending at zero")
        if thresholds[0] > self.max_score:
            raise ValueError("severity band threshold cannot exceed max_score")
        return self


class RiskExplanation(BaseModel):
    policy_version: str
    strongest_signal_type: str
    strongest_signal_weight: int
    severity_points: float
    exposure_ratio: float
    exposure_points: float
    criticality_bonus: int
    unbounded_score: float
    score_cap_applied: bool


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
    risk_explanation: RiskExplanation
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
