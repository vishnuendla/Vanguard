from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_production_config_requires_an_explicit_token() -> None:
    project_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["VANGUARD_ENV"] = "production"
    environment["VANGUARD_API_TOKEN"] = ""
    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "VANGUARD_API_TOKEN is required" in result.stderr


def test_development_config_requires_explicit_demo_opt_in() -> None:
    project_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["VANGUARD_API_TOKEN"] = ""
    environment["VANGUARD_ENV"] = "development"
    environment["VANGUARD_DEMO_MODE"] = ""
    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "VANGUARD_DEMO_MODE=true" in result.stderr


def test_development_config_retains_the_explicit_demo_token() -> None:
    project_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["VANGUARD_API_TOKEN"] = ""
    environment["VANGUARD_ENV"] = "development"
    environment["VANGUARD_DEMO_MODE"] = "true"
    result = subprocess.run(
        [sys.executable, "-c", "from app.config import API_TOKEN; print(API_TOKEN)"],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "local-demo-token"
