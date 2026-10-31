from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"

# Documented local-demo credential. Deployments must set VANGUARD_API_TOKEN.
DEMO_API_TOKEN = "local-demo-token"  # nosec B105
API_TOKEN = os.getenv("VANGUARD_API_TOKEN", DEMO_API_TOKEN).strip()
if not API_TOKEN:
    raise RuntimeError("VANGUARD_API_TOKEN must not be empty")

DATABASE_PATH = Path(
    os.getenv("VANGUARD_DATABASE_PATH", str(DATA_DIR / "vanguard.db"))
).expanduser()
