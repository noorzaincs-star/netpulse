from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from netpulse.models import Base


def create_database_engine(database_url: str) -> AsyncEngine:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine.sync_engine, "connect")
        def enable_sqlite_foreign_keys(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


async def initialize_database(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_migrate_device_check_settings)


def _migrate_device_check_settings(connection: Connection) -> None:
    columns = {
        column["name"]
        for column in inspect(connection).get_columns("devices")
    }
    if "ping_count" not in columns:
        connection.execute(
            text("ALTER TABLE devices ADD COLUMN ping_count INTEGER NOT NULL DEFAULT 3")
        )
    if "check_timeout_seconds" not in columns:
        connection.execute(
            text(
                "ALTER TABLE devices ADD COLUMN "
                "check_timeout_seconds FLOAT NOT NULL DEFAULT 3.0"
            )
        )
