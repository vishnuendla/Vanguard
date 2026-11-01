from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from app.database import audit_events, initialize, status_map, update_status


def test_concurrent_status_updates_keep_a_serial_audit_chain(tmp_path: Path) -> None:
    database_path = tmp_path / "concurrent.db"
    initialize(database_path)
    barrier = Barrier(2)

    def update(status: str) -> dict:
        barrier.wait(timeout=5)
        return update_status(
            "inc-vendor-a", "vendor-a", status, "analyst", f"Move to {status}.", database_path
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(update, ("reviewed", "relevant")))

    assert {event["new_status"] for event in results} == {"reviewed", "relevant"}
    chronological = list(reversed(audit_events(database_path, "inc-vendor-a")))
    assert len(chronological) == 2
    assert chronological[0]["old_status"] == "new"
    assert chronological[1]["old_status"] == chronological[0]["new_status"]
    assert status_map(database_path)["vendor-a"] == chronological[-1]["new_status"]
