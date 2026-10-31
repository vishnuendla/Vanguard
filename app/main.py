from __future__ import annotations

import hmac
import json
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import API_TOKEN, ROOT
from app.database import audit_events, initialize, status_map, update_status
from app.engine import load_incidents
from app.schemas import IncidentStatus, StatusUpdate


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize()
    yield


app = FastAPI(
    title="Vanguard API",
    description="Evidence-led vendor and supply disruption triage.",
    version="0.1.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")


def authenticated(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> str:
    scheme, _, supplied = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not supplied or not hmac.compare_digest(supplied, API_TOKEN):
        raise HTTPException(status_code=401, detail="Valid bearer token required")
    actor = (x_user_id or "").strip()
    if not actor or len(actor) > 100:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")
    return actor


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "vanguard"}


@app.get("/api/config")
def public_config() -> dict[str, str]:
    from app.config import API_TOKEN as current_token

    # Only disclose the known development token. A deployment token is never sent to clients.
    return {"demo_token": current_token if current_token == "local-demo-token" else ""}  # nosec B105


@app.get("/api/vendors")
def vendors(_: str = Depends(authenticated)) -> list[dict]:
    with (ROOT / "data" / "vendors.json").open(encoding="utf-8") as handle:
        return json.load(handle)


@app.get("/api/incidents")
def incidents(
    status: Annotated[IncidentStatus | None, Query()] = None,
    _: str = Depends(authenticated),
) -> list:
    items = load_incidents(status_map())
    if status:
        items = [item for item in items if item.status == status]
    return items


@app.get("/api/incidents/{incident_id}")
def incident_detail(incident_id: str, _: str = Depends(authenticated)) -> dict:
    for item in load_incidents(status_map()):
        if item.id == incident_id:
            return item.model_dump()
    raise HTTPException(status_code=404, detail="Incident not found")


@app.patch("/api/incidents/{incident_id}/status")
def set_incident_status(
    incident_id: str, update: StatusUpdate, actor: str = Depends(authenticated),
) -> dict:
    incident = next((item for item in load_incidents(status_map()) if item.id == incident_id), None)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    event = update_status(incident_id, incident.vendor_id, update.status, actor, update.rationale)
    return {"incident": incident_id, "status": update.status, "audit_event": event}


@app.get("/api/audit")
def audit(
    incident_id: Annotated[str | None, Query(max_length=100)] = None,
    _: str = Depends(authenticated),
) -> list[dict]:
    return audit_events(incident_id=incident_id)
