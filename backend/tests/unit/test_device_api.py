from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from netpulse.core.config import Settings
from netpulse.main import create_app


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'devices.sqlite3'}",
            max_devices=2,
        ),
        start_worker=False,
    )
    with TestClient(app, base_url="http://127.0.0.1") as test_client:
        yield test_client


def create_device(client: TestClient, **overrides: object):
    data = {
        "name": "Office router",
        "hostname": "192.0.2.1",
        "device_type": "router",
        "tags": ["office"],
        "interval_seconds": 30,
        "check_types": ["icmp"],
    }
    data.update(overrides)
    return client.post("/api/devices", json=data)


def test_device_crud_and_pause_resume(client: TestClient) -> None:
    created = create_device(client)
    assert created.status_code == 201
    device = created.json()
    assert device["hostname"] == "192.0.2.1"
    assert device["state"] == "UNKNOWN"

    fetched = client.get(f"/api/devices/{device['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Office router"

    patched = client.patch(
        f"/api/devices/{device['id']}",
        json={"name": "Updated router", "interval_seconds": 90},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Updated router"
    assert patched.json()["interval_seconds"] == 90

    paused = client.post(f"/api/devices/{device['id']}/pause")
    assert paused.status_code == 200
    assert paused.json()["state"] == "PAUSED"
    resumed = client.post(f"/api/devices/{device['id']}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["state"] == "UNKNOWN"

    deleted = client.delete(f"/api/devices/{device['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/devices/{device['id']}").status_code == 404


def test_device_validation_and_limit(client: TestClient) -> None:
    assert create_device(client, hostname="host;whoami").status_code == 422
    assert create_device(client, ping_count=11).status_code == 422
    assert create_device(client, check_types=["tcp"]).status_code == 422
    assert create_device(client, check_types=["tcp"], tcp_port=443).status_code == 201
    assert create_device(client, name="Second", hostname="192.0.2.2").status_code == 201
    assert create_device(client, name="Third", hostname="192.0.2.3").status_code == 409


def test_empty_patch_and_bad_pagination_return_validation_errors(client: TestClient) -> None:
    device = create_device(client).json()
    assert client.patch(f"/api/devices/{device['id']}", json={}).status_code == 422
    response = client.get("/api/devices?page=0")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_manual_check_response_is_persisted(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime, timezone

    from netpulse.checks.result import CheckResult, CheckStatus

    ping_options: dict[str, object] = {}

    async def fake_ping(host: str, **kwargs: object) -> CheckResult:
        ping_options.update(kwargs)
        return CheckResult.create(
            "icmp",
            CheckStatus.SUCCESS,
            datetime.now(timezone.utc),
            latency_ms=4.2,
            packet_loss_percent=0,
            details={"target": host, "attempts": 1, "replies": 1},
        )

    monkeypatch.setattr("netpulse.services.monitoring.ping_host", fake_ping)
    device = create_device(
        client,
        ping_count=4,
        check_timeout_seconds=1.5,
    ).json()
    assert device["ping_count"] == 4
    assert device["check_timeout_seconds"] == 1.5
    response = client.post(
        f"/api/devices/{device['id']}/check",
        json={"ping_count": 2, "timeout_seconds": 2.0},
    )
    assert response.status_code == 200
    assert response.json()["measurements"][0]["latency_ms"] == 4.2
    assert ping_options == {"count": 2, "timeout_seconds": 2.0}
    history = client.get(f"/api/devices/{device['id']}/measurements")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["outcome"] == "success"


def test_unknown_device_check_returns_404(client: TestClient) -> None:
    response = client.post("/api/devices/missing/check", json={})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "device_not_found"
