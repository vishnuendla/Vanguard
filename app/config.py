from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"

# Documented local-demo credential. It is enabled only with an explicit opt-in.
DEMO_API_TOKEN = "local-demo-token"  # nosec B105
RUNTIME_ENV = os.getenv("VANGUARD_ENV", "development").strip().lower()
configured_token = os.getenv("VANGUARD_API_TOKEN", "").strip()
DEMO_MODE = os.getenv("VANGUARD_DEMO_MODE", "").strip().lower() == "true"

if configured_token:
    API_TOKEN = configured_token
elif DEMO_MODE and RUNTIME_ENV != "production":
    API_TOKEN = DEMO_API_TOKEN
elif RUNTIME_ENV == "production":
    raise RuntimeError("VANGUARD_API_TOKEN is required when VANGUARD_ENV=production")
else:
    raise RuntimeError(
        "VANGUARD_API_TOKEN is required unless VANGUARD_DEMO_MODE=true in development"
    )

# A shared bearer token identifies a service account, not an individual user.
AUDIT_ACTOR = os.getenv("VANGUARD_AUDIT_ACTOR", "").strip() or (
    "local-demo-analyst" if DEMO_MODE else "shared-api-token"
)

try:
    RATE_LIMIT_PER_MINUTE = int(os.getenv("VANGUARD_RATE_LIMIT_PER_MINUTE", "120"))
except ValueError as error:
    raise RuntimeError("VANGUARD_RATE_LIMIT_PER_MINUTE must be a positive integer") from error
if RATE_LIMIT_PER_MINUTE < 1:
    raise RuntimeError("VANGUARD_RATE_LIMIT_PER_MINUTE must be a positive integer")

DATABASE_PATH = Path(
    os.getenv("VANGUARD_DATABASE_PATH", str(DATA_DIR / "vanguard.db"))
).expanduser()
