from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DATA_DIR = ROOT / "data"
DATABASE_PATH = Path(os.getenv("VANGUARD_DATABASE_PATH", str(DATA_DIR / "vanguard.db")))
API_TOKEN = os.getenv("VANGUARD_API_TOKEN", "local-demo-token")
