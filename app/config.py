from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"

# Documented local-demo credential. Production containers must set VANGUARD_API_TOKEN.
DEMO_API_TOKEN = "local-demo-token"  # nosec B105
RUNTIME_ENV = os.getenv("VANGUARD_ENV", "development").strip().lower()
configured_token = os.getenv("VANGUARD_API_TOKEN", "").strip()
if RUNTIME_ENV == "production" and not configured_token:
    raise RuntimeError("VANGUARD_API_TOKEN is required when VANGUARD_ENV=production")

API_TOKEN = configured_token or DEMO_API_TOKEN
if not API_TOKEN:
    raise RuntimeError("VANGUARD_API_TOKEN must not be empty")

DATABASE_PATH = Path(
    os.getenv("VANGUARD_DATABASE_PATH", str(DATA_DIR / "vanguard.db"))
).expanduser()
