from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import (
    API_TOKEN,
    AUDIT_ACTOR,
    DEMO_API_TOKEN,
    DEMO_MODE,
    RATE_LIMIT_PER_MINUTE,
    ROOT,
)
from app.database import (
    MAX_AUDIT_ROWS,
    StatusConflictError,
    audit_events,
    initialize,
    status_map,
    update_status,
)
from app.engine import load_incidents, load_risk_policy, load_vendors
from app.rate_limit import RateLimiter
from app.schemas import (
    AuditEvent,
    HealthResponse,
    Incident,
    IncidentStatus,
    PublicConfig,
    RiskPolicy,
    StatusUpdate,
    StatusUpdateResponse,
    Vendor,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize()
    load_incidents()
    yield


app = FastAPI(
    title="Vanguard API",
    description="Evidence-led vendor and supply disruption triage.",
    version=__version__,
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")
rate_limiter = RateLimiter(limit=RATE_LIMIT_PER_MINUTE)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    protected_api = request.url.path.startswith("/api/") and request.url.path not in {
        "/api/health",
        "/api/config",
    }
    client_address = request.client.host if request.client else "unknown"
    if protected_api and not rate_limiter.allow(client_address):
        response = JSONResponse(
            status_code=429,
            content={"detail": "Too many requests; try again in one minute"},
            headers={"Retry-After": "60"},
        )
    else:
        response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; "
        "img-src 'self' data:; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; connect-src 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def authenticated(
    authorization: str | None = Header(default=None),
) -> str:
    scheme, _, supplied = (authorization or "").partition(" ")
    valid_token = bool(supplied) and hmac.compare_digest(supplied, API_TOKEN)
    if scheme.lower() != "bearer" or not valid_token:
        raise HTTPException(
            status_code=401,
            detail="Valid bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AUDIT_ACTOR


def _incident_or_404(incident_id: str) -> Incident:
    incident = next((item for item in load_incidents(status_map()) if item.id == incident_id), None)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(ROOT / "web" / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="vanguard")


@app.get("/api/config", response_model=PublicConfig)
def public_config() -> PublicConfig:
    # Only disclose the known development token. A deployment token is never sent to clients.
    demo_token = API_TOKEN if DEMO_MODE and API_TOKEN == DEMO_API_TOKEN else ""
    return PublicConfig(demo_token=demo_token)


@app.get("/api/vendors", response_model=list[Vendor])
def vendors(_: str = Depends(authenticated)) -> list[Vendor]:
    return load_vendors()


@app.get("/api/risk-policy", response_model=RiskPolicy)
def risk_policy(_: str = Depends(authenticated)) -> RiskPolicy:
    return load_risk_policy()


@app.get("/api/incidents", response_model=list[Incident])
def incidents(
    status: Annotated[IncidentStatus | None, Query()] = None,
    _: str = Depends(authenticated),
) -> list[Incident]:
    items = load_incidents(status_map())
    if status:
        items = [item for item in items if item.status == status]
    return items


@app.get("/api/incidents/{incident_id}", response_model=Incident)
def incident_detail(incident_id: str, _: str = Depends(authenticated)) -> Incident:
    return _incident_or_404(incident_id)


@app.patch(
    "/api/incidents/{incident_id}/status",
    response_model=StatusUpdateResponse,
    responses={409: {"description": "Requested status matches the current status"}},
)
def set_incident_status(
    incident_id: str,
    update: StatusUpdate,
    actor: str = Depends(authenticated),
) -> StatusUpdateResponse:
    incident = _incident_or_404(incident_id)
    try:
        event = update_status(
            incident_id,
            incident.vendor_id,
            update.status,
            actor,
            update.rationale,
        )
    except StatusConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return StatusUpdateResponse(
        incident=incident_id,
        status=update.status,
        audit_event=AuditEvent.model_validate(event),
    )


@app.get("/api/audit", response_model=list[AuditEvent])
def audit(
    incident_id: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_AUDIT_ROWS)] = 100,
    _: str = Depends(authenticated),
) -> list[AuditEvent]:
    return [
        AuditEvent.model_validate(event)
        for event in audit_events(incident_id=incident_id, limit=limit)
    ]
