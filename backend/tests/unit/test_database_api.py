from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from netpulse.core.config import Settings
from netpulse.main import create_app
from netpulse.models import Device


def test_health_endpoint_initializes_database_and_openapi(tmp_path) -> None:
    database_path = tmp_path / "health.sqlite3"
    app = create_app(Settings(database_url=f"sqlite+aiosqlite:///{database_path}"))

    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get("/api/health")
        openapi = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "version": "0.1.0"}
    assert "/api/health" in openapi.json()["paths"]
    assert database_path.exists()


@pytest.mark.asyncio
async def test_device_record_persists_across_database_sessions(tmp_path: Path) -> None:
    from netpulse.db.database import create_database_engine, initialize_database

    engine = create_database_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'persist.sqlite3'}"
    )
    await initialize_database(engine)
    async with engine.connect() as connection:
        assert await connection.scalar(text("PRAGMA foreign_keys")) == 1
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    timestamp = datetime.now(timezone.utc)
    async with sessions() as session:
        session.add(
            Device(
                name="Local test target",
                hostname="127.0.0.1",
                device_type="server",
                enabled=True,
                interval_seconds=60,
                tags=[],
                check_types=["tcp"],
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        await session.commit()
    async with sessions() as session:
        devices = (await session.scalars(select(Device))).all()
        assert len(devices) == 1
        assert devices[0].hostname == "127.0.0.1"
    await engine.dispose()


@pytest.mark.asyncio
async def test_initialize_database_adds_check_settings_to_existing_device_table(
    tmp_path: Path,
) -> None:
    from netpulse.db.database import create_database_engine, initialize_database

    engine = create_database_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'upgrade.sqlite3'}"
    )
    async with engine.begin() as connection:
        await connection.exec_driver_sql(
            "CREATE TABLE devices (id VARCHAR(36) PRIMARY KEY)"
        )

    await initialize_database(engine)
    async with engine.connect() as connection:
        columns = {
            row[1]
            for row in await connection.exec_driver_sql("PRAGMA table_info(devices)")
        }
    await engine.dispose()

    assert {"ping_count", "check_timeout_seconds"} <= columns
