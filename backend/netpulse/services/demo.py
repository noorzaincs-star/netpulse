from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from netpulse.core.config import PUBLIC_DEMO_TARGETS
from netpulse.models import Device


_DEMO_DEVICES = (
    {
        "name": "Google",
        "hostname": "google.com",
        "device_type": "service",
        "description": "Public DNS name. Measurements are from actual scheduled probes.",
        "check_types": ["tcp", "dns"],
        "tcp_port": 443,
    },
    {
        "name": "Google Public DNS",
        "hostname": "8.8.8.8",
        "device_type": "dns",
        "description": "Public DNS resolver address. Measurements are from actual scheduled probes.",
        "check_types": ["tcp"],
        "tcp_port": 443,
    },
)


async def seed_public_demo_devices(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as session:
        existing_devices = (
            await session.scalars(
                select(Device).where(Device.hostname.in_(PUBLIC_DEMO_TARGETS))
            )
        ).all()
        existing_by_host = {device.hostname: device for device in existing_devices}
        now = datetime.now(timezone.utc)
        for values in _DEMO_DEVICES:
            device = existing_by_host.get(values["hostname"])
            if device is not None:
                for field, value in values.items():
                    setattr(device, field, value)
                device.tags = ["public-demo"]
                device.enabled = True
                device.interval_seconds = 60
                device.ping_count = 1
                device.check_timeout_seconds = 3.0
                device.dns_record_type = "A"
                device.state = "UNKNOWN"
                device.failure_count = 0
                device.recovery_count = 0
                device.check_failures = {}
                device.updated_at = now
                continue
            session.add(
                Device(
                    **values,
                    tags=["public-demo"],
                    enabled=True,
                    interval_seconds=60,
                    ping_count=1,
                    check_timeout_seconds=3.0,
                    dns_record_type="A",
                    state="UNKNOWN",
                    failure_count=0,
                    recovery_count=0,
                    check_failures={},
                    created_at=now,
                    updated_at=now,
                )
            )
        await session.commit()
