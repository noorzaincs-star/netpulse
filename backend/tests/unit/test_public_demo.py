from datetime import datetime, timezone
from pathlib import Path
import secrets

import pytest
from fastapi.testclient import TestClient

from netpulse.core.config import PUBLIC_DEMO_TARGETS, Settings
from netpulse.main import create_app
from netpulse.models import Device, Incident, Measurement


@pytest.fixture
def demo_app(tmp_path: Path):
    admin_token = secrets.token_urlsafe(32)
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'public-demo.sqlite3'}",
            public_demo_mode=True,
            admin_token=admin_token,
        ),
        start_worker=False,
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield app, client


def _admin_headers(app) -> dict[str, str]:
    token = app.state.settings.admin_token
    assert token is not None
    return {"Authorization": f"Bearer {token}"}


def _insert_private_records(app, client: TestClient, *, with_history: bool) -> str:
    async def insert() -> str:
        now = datetime.now(timezone.utc)
        async with app.state.sessions() as session:
            private_device = Device(
                name="Private device",
                hostname="internal.example",
                device_type="server",
                tags=[],
                enabled=True,
                interval_seconds=60,
                check_types=["icmp"],
                ping_count=1,
                check_timeout_seconds=3,
                dns_record_type="A",
                state="UNKNOWN",
                failure_count=0,
                recovery_count=0,
                check_failures={},
                created_at=now,
                updated_at=now,
            )
            session.add(private_device)
            await session.flush()
            if with_history:
                session.add(
                    Measurement(
                        device_id=private_device.id,
                        check_type="icmp",
                        outcome="success",
                        started_at=now,
                        completed_at=now,
                        latency_ms=1,
                        packet_loss_percent=0,
                        details={"target": "internal.example"},
                    )
                )
                session.add(
                    Incident(
                        device_id=private_device.id,
                        kind="unavailable",
                        severity="warning",
                        status="active",
                        deduplication_key=f"{private_device.id}:unavailable",
                        started_at=now,
                        supporting_measurements=[],
                        observed_facts={},
                    )
                )
            await session.commit()
            return private_device.id

    return client.portal.call(insert)


def test_public_demo_seeds_only_real_targets_and_exposes_no_secret(demo_app) -> None:
    _, client = demo_app

    response = client.get("/api/devices")
    assert response.status_code == 200
    assert {device["hostname"] for device in response.json()["items"]} == PUBLIC_DEMO_TARGETS

    settings = client.get("/api/settings").json()
    assert settings["demo_mode"] is True
    assert set(settings["demo_targets"]) == PUBLIC_DEMO_TARGETS
    assert "admin_token" not in settings
    assert client.get("/api/measurements").json()["total"] == 0
    devices = {device["hostname"]: device for device in response.json()["items"]}
    assert devices["google.com"]["check_types"] == ["tcp", "dns"]
    assert devices["google.com"]["tcp_port"] == 443
    assert devices["8.8.8.8"]["check_types"] == ["tcp"]
    assert devices["8.8.8.8"]["tcp_port"] == 443
    assert all("icmp" not in device["check_types"] for device in devices.values())
    interfaces = client.get("/api/interfaces").json()
    assert interfaces["interfaces"] == []
    assert "not exposed" in interfaces["note"]


def test_public_demo_rejects_device_creation_and_manual_checks(demo_app) -> None:
    app, client = demo_app
    payload = {
        "name": "Unauthorized target",
        "hostname": "example.com",
        "check_types": ["icmp"],
    }

    assert client.post("/api/devices", json=payload).status_code == 401
    denied_create = client.post(
        "/api/devices",
        json=payload,
        headers=_admin_headers(app),
    )
    assert denied_create.status_code == 422
    assert denied_create.json()["error"]["code"] == "demo_target_not_allowed"

    device = client.get("/api/devices").json()["items"][0]
    assert client.post(
        f"/api/devices/{device['id']}/check",
        json={},
    ).status_code == 401


def test_admin_token_protects_mutations_and_hostname_is_allowlisted(
    demo_app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client = demo_app
    device = client.get("/api/devices").json()["items"][0]

    assert client.patch(
        f"/api/devices/{device['id']}",
        json={"name": "Changed without admin"},
    ).status_code == 401

    denied = client.patch(
        f"/api/devices/{device['id']}",
        json={"hostname": "example.com"},
        headers=_admin_headers(app),
    )
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "demo_target_not_allowed"

    updated = client.patch(
        f"/api/devices/{device['id']}",
        json={"name": "Admin-updated allowed target"},
        headers=_admin_headers(app),
    )
    assert updated.status_code == 200

    async def completed_check(*args, **kwargs):
        return []

    monkeypatch.setattr(app.state.monitoring, "run_device", completed_check)
    authorized_check = client.post(
        f"/api/devices/{device['id']}/check",
        json={},
        headers=_admin_headers(app),
    )
    assert authorized_check.status_code == 200

    protected_writes = (
        ("post", f"/api/devices/{device['id']}/pause", None),
        ("post", f"/api/devices/{device['id']}/resume", None),
        ("delete", f"/api/devices/{device['id']}", None),
        (
            "post",
            "/api/topology/links",
            {"source_device_id": device["id"], "target_device_id": "missing"},
        ),
        ("delete", "/api/topology/links/missing", None),
    )
    for method, path, payload in protected_writes:
        if method == "post" and payload is not None:
            response = client.post(path, json=payload)
        elif method == "post":
            response = client.post(path)
        else:
            response = client.delete(path)
        assert response.status_code == 401


def test_demo_reads_hide_non_allowlisted_devices_and_measurements(demo_app) -> None:
    app, client = demo_app
    private_id = _insert_private_records(app, client, with_history=True)

    assert client.get("/api/devices").json()["total"] == 2
    assert client.get(f"/api/devices/{private_id}").status_code == 404
    assert client.get("/api/measurements").json()["total"] == 0
    assert client.get("/api/incidents").json()["total"] == 0
    assert all(
        node["hostname"] in PUBLIC_DEMO_TARGETS
        for node in client.get("/api/topology").json()["nodes"]
    )


def test_monitoring_service_refuses_non_allowlisted_target(demo_app) -> None:
    app, client = demo_app
    private_id = _insert_private_records(app, client, with_history=False)

    with pytest.raises(PermissionError, match="restricted to google.com and 8.8.8.8"):
        client.portal.call(app.state.monitoring.run_device, private_id)


def test_public_demo_websocket_filters_non_allowlisted_device_events(demo_app) -> None:
    app, client = demo_app
    private_id = _insert_private_records(app, client, with_history=False)
    public_id = client.get("/api/devices").json()["items"][0]["id"]

    with client.websocket_connect(
        "/api/ws",
        headers={"origin": "http://127.0.0.1:5173"},
    ) as websocket:
        client.portal.call(
            app.state.broker.publish,
            {"type": "measurement.created", "device_id": private_id},
        )
        client.portal.call(
            app.state.broker.publish,
            {"type": "measurement.created", "device_id": public_id},
        )
        event = websocket.receive_json()

    assert event["device_id"] == public_id
