from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["VANGUARD_ENV"] = "development"
os.environ["VANGUARD_DEMO_MODE"] = "true"
os.environ.pop("VANGUARD_API_TOKEN", None)

from app import database
from app.main import app, rate_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    rate_limiter.reset()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "test.db"
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer local-demo-token"}
