import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from netpulse.core.config import PUBLIC_DEMO_TARGETS, Settings
from netpulse.models import Device, Measurement
from netpulse.services.monitoring import MonitoringService

logger = logging.getLogger(__name__)


class MonitoringWorker:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        service: MonitoringService,
        settings: Settings,
    ) -> None:
        self.sessions = sessions
        self.service = service
        self.settings = settings
        self._task: asyncio.Task[None] | None = None
        self._next_due: dict[str, float] = {}
        self._running: dict[str, asyncio.Task[None]] = {}
        self._last_retention = 0.0

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="netpulse-monitor")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        active = list(self._running.values())
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        self._running.clear()
        self._task = None

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            try:
                async with self.sessions() as session:
                    query = select(Device).where(Device.enabled.is_(True))
                    if self.settings.public_demo_mode:
                        query = query.where(Device.hostname.in_(PUBLIC_DEMO_TARGETS))
                    devices = (await session.scalars(query)).all()
                enabled_ids = {device.id for device in devices}
                self._next_due = {
                    device_id: due
                    for device_id, due in self._next_due.items()
                    if device_id in enabled_ids
                }
                now = loop.time()
                for device in devices:
                    due = self._next_due.setdefault(device.id, now)
                    if due <= now and device.id not in self._running:
                        self._next_due[device.id] = now + device.interval_seconds
                        task = asyncio.create_task(
                            self._check_device(device.id),
                            name=f"netpulse-check-{device.id}",
                        )
                        self._running[device.id] = task
                if now - self._last_retention >= 3600:
                    self._last_retention = now
                    await self._prune_measurements()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Monitoring scheduler iteration failed")
                await asyncio.sleep(2)

    async def _check_device(self, device_id: str) -> None:
        try:
            await self.service.run_device(device_id)
        except asyncio.CancelledError:
            raise
        except (LookupError, PermissionError):
            logger.info("Skipping removed or paused device", extra={"device_id": device_id})
        except Exception:
            logger.exception("Scheduled device check failed", extra={"device_id": device_id})
        finally:
            self._running.pop(device_id, None)

    async def _prune_measurements(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=self.settings.measurement_retention_days
        )
        async with self.sessions() as session:
            ids = (
                await session.scalars(
                    select(Measurement.id)
                    .where(Measurement.completed_at < cutoff)
                    .order_by(Measurement.completed_at)
                    .limit(1000)
                )
            ).all()
            if ids:
                await session.execute(delete(Measurement).where(Measurement.id.in_(ids)))
                await session.commit()
                logger.info("Pruned old measurements", extra={"deleted": len(ids)})
