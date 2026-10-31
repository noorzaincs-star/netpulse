from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from netpulse.core.config import Settings
from netpulse.main import create_app


def _client(tmp_path: Path) -> TestClient:
    app = create_app(
        Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'live.sqlite3'}"),
        start_worker=False,
    )
    return TestClient(app, base_url="http://127.0.0.1")


def test_websocket_delivers_events_for_an_allowed_origin(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        with client.websocket_connect(
            "/api/ws",
            headers={"origin": "http://127.0.0.1:5173"},
        ) as websocket:
            response = client.post(
                "/api/devices",
                json={
                    "name": "Allowed target",
                    "hostname": "192.0.2.20",
                    "check_types": ["icmp"],
                },
            )
            assert response.status_code == 201
            event = websocket.receive_json()
            assert event["type"] == "device.updated"
            assert event["device"]["id"] == response.json()["id"]


def test_websocket_rejects_an_untrusted_origin(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                "/api/ws",
                headers={"origin": "https://untrusted.example"},
            ):
                pass
        assert error.value.code == 1008


def test_http_accepts_configured_render_hostname(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'render.sqlite3'}",
        allowed_hosts=("localhost", "127.0.0.1", "::1", "netpulse-api.onrender.com"),
    )
    app = create_app(settings, start_worker=False)

    with TestClient(app, base_url="https://netpulse-api.onrender.com") as client:
        response = client.get("/api/health")

    assert response.status_code == 200
