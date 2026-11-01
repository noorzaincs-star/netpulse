from pathlib import Path

from fastapi.testclient import TestClient

from netpulse.core.config import Settings
from netpulse.main import create_app


def test_static_frontend_and_api_share_one_origin(tmp_path: Path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>NetPulse frontend</html>", encoding="utf-8")
    app = create_app(
        Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'static.sqlite3'}"),
        start_worker=False,
        static_dir=static_dir,
    )

    with TestClient(app, base_url="http://127.0.0.1") as client:
        page = client.get("/")
        health = client.get("/api/health")

    assert page.status_code == 200
    assert "NetPulse frontend" in page.text
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
