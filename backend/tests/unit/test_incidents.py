from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from netpulse.checks.result import CheckResult, CheckStatus
from netpulse.core.config import Settings
from netpulse.main import create_app


def _result(host: str, outcome: CheckStatus) -> CheckResult:
    return CheckResult.create(
        "icmp",
        outcome,
        datetime.now(timezone.utc),
        latency_ms=8.0 if outcome is CheckStatus.SUCCESS else None,
        packet_loss_percent=0 if outcome is CheckStatus.SUCCESS else 100,
        details={"target": host},
        error="No echo reply" if outcome is not CheckStatus.SUCCESS else None,
    )


def test_failure_threshold_deduplicates_and_recovery_confirms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcomes = [
        CheckStatus.FAILURE,
        CheckStatus.FAILURE,
        CheckStatus.SUCCESS,
        CheckStatus.FAILURE,
        CheckStatus.SUCCESS,
        CheckStatus.SUCCESS,
    ]

    async def fake_ping(host: str, **kwargs: object) -> CheckResult:
        return _result(host, outcomes.pop(0))

    monkeypatch.setattr("netpulse.services.monitoring.ping_host", fake_ping)
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'incidents.sqlite3'}",
            failure_threshold=2,
            recovery_threshold=2,
        ),
        start_worker=False,
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        created = client.post(
            "/api/devices",
            json={
                "name": "Authorized test target",
                "hostname": "192.0.2.10",
                "check_types": ["icmp"],
                "interval_seconds": 30,
            },
        )
        device_id = created.json()["id"]
        first = client.post(f"/api/devices/{device_id}/check", json={})
        second = client.post(f"/api/devices/{device_id}/check", json={})
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert [item["outcome"] for item in second.json()["measurements"]] == ["failure"]
        incidents = client.get("/api/incidents?status=active").json()["items"]

        assert len(incidents) == 2
        assert {item["kind"] for item in incidents} == {"icmp_failure", "unavailable"}
        assert client.get(f"/api/devices/{device_id}").json()["state"] == "DOWN"

        client.post(f"/api/devices/{device_id}/check", json={})
        assert client.get(f"/api/devices/{device_id}").json()["state"] == "DOWN"
        assert len(client.get("/api/incidents?status=active").json()["items"]) == 2
        client.post(f"/api/devices/{device_id}/check", json={})
        assert len(client.get("/api/incidents?status=active").json()["items"]) == 2
        client.post(f"/api/devices/{device_id}/check", json={})
        assert client.get(f"/api/devices/{device_id}").json()["state"] == "UP"
        assert len(client.get("/api/incidents?status=active").json()["items"]) == 2
        client.post(f"/api/devices/{device_id}/check", json={})
        recovered = client.get("/api/incidents?status=recovered").json()["items"]
        assert len(recovered) == 2
        assert all(item["recovered_at"] for item in recovered)
