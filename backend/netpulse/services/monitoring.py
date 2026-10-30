import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from netpulse.checks.dns import query_dns
from netpulse.checks.ping import ping_host
from netpulse.checks.result import CheckResult, CheckStatus
from netpulse.checks.tcp import check_tcp
from netpulse.core.config import Settings
from netpulse.models import Device, Incident, Measurement
from netpulse.schemas.devices import CheckType, DeviceState
from netpulse.services.events import EventBroker
from netpulse.services.incidents import open_incident, recover_incident, utc_now

logger = logging.getLogger(__name__)


class MonitoringService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        settings: Settings,
        broker: EventBroker,
    ) -> None:
        self.sessions = sessions
        self.settings = settings
        self.broker = broker
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._active_devices: set[str] = set()

    async def run_device(
        self,
        device_id: str,
        *,
        timeout_seconds: float | None = None,
        ping_count: int | None = None,
    ) -> list[Measurement]:
        if device_id in self._active_devices:
            raise RuntimeError("A check is already running for this device.")
        self._active_devices.add(device_id)
        try:
            async with self.sessions() as session:
                device = await session.get(Device, device_id)
                if device is None:
                    raise LookupError("Device not found.")
                if not device.enabled:
                    raise PermissionError("Paused devices cannot be checked.")
                snapshot = {
                    "id": device.id,
                    "hostname": device.hostname,
                    "check_types": list(device.check_types),
                    "ping_count": device.ping_count,
                    "check_timeout_seconds": device.check_timeout_seconds,
                    "tcp_port": device.tcp_port,
                    "dns_record_type": device.dns_record_type,
                }

            effective_timeout = (
                timeout_seconds
                if timeout_seconds is not None
                else snapshot["check_timeout_seconds"]
            )
            effective_ping_count = (
                ping_count if ping_count is not None else snapshot["ping_count"]
            )
            results = await asyncio.gather(
                *(
                    self._run_check(
                        snapshot,
                        check_type,
                        effective_timeout,
                        effective_ping_count,
                    )
                    for check_type in snapshot["check_types"]
                )
            )
            return await self._persist_cycle(device_id, results)
        finally:
            self._active_devices.discard(device_id)

    async def _run_check(
        self,
        device: dict[str, Any],
        check_type: str,
        timeout_seconds: float,
        ping_count: int,
    ) -> CheckResult:
        async with self._semaphore:
            try:
                if check_type == CheckType.ICMP:
                    return await ping_host(
                        device["hostname"],
                        count=ping_count,
                        timeout_seconds=timeout_seconds,
                    )
                if check_type == CheckType.TCP:
                    return await check_tcp(
                        device["hostname"],
                        device["tcp_port"],
                        timeout_seconds=timeout_seconds,
                    )
                if check_type == CheckType.DNS:
                    return await query_dns(
                        device["hostname"],
                        device["dns_record_type"],
                        timeout_seconds=timeout_seconds,
                    )
                raise ValueError(f"Unsupported configured check type: {check_type}")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Network check adapter failed", extra={"check_type": check_type})
                return CheckResult.create(
                    check_type,
                    CheckStatus.PROCESS_ERROR,
                    datetime.now(timezone.utc),
                    details={"target": device["hostname"]},
                    error=f"Check adapter error: {exc}",
                )

    async def _persist_cycle(
        self,
        device_id: str,
        results: list[CheckResult],
    ) -> list[Measurement]:
        events: list[dict[str, Any]] = []
        async with self.sessions() as session:
            device = await session.get(Device, device_id)
            if device is None:
                raise LookupError("Device was deleted while a check was running.")

            measurements: list[Measurement] = []
            for result in results:
                measurement = Measurement(
                    device_id=device_id,
                    check_type=result.check_type,
                    outcome=result.status.value,
                    started_at=result.started_at,
                    completed_at=result.completed_at,
                    latency_ms=result.latency_ms,
                    packet_loss_percent=result.packet_loss_percent,
                    details=result.details,
                    error=result.error,
                )
                session.add(measurement)
                measurements.append(measurement)
            await session.flush()

            successful = [item for item in measurements if item.outcome == CheckStatus.SUCCESS]
            failures = [item for item in measurements if item.outcome != CheckStatus.SUCCESS]
            previous_state = device.state
            check_failures = dict(device.check_failures)
            device.last_checked_at = utc_now()
            device.updated_at = device.last_checked_at

            for measurement in measurements:
                check_key = measurement.check_type
                if measurement.outcome == CheckStatus.SUCCESS:
                    check_failures.pop(check_key, None)
                    await self._recover_check_incident(
                        session, device, measurement, events
                    )
                else:
                    await self._reset_check_recovery(
                        session, device_id, check_key
                    )
                    check_failures[check_key] = check_failures.get(check_key, 0) + 1
                    if check_failures[check_key] >= self.settings.failure_threshold:
                        incident, created = await open_incident(
                            session,
                            device_id=device_id,
                            kind=f"{check_key}_failure",
                            severity="warning",
                            deduplication_key=f"{device_id}:{check_key}_failure",
                            facts={
                                "check_type": check_key,
                                "outcome": measurement.outcome,
                                "consecutive_failures": check_failures[check_key],
                                "error": measurement.error,
                            },
                            measurement_id=measurement.id,
                        )
                        if created:
                            events.append(self._incident_event("incident.created", incident))

                if measurement.outcome == CheckStatus.SUCCESS and measurement.latency_ms is not None:
                    kind = "high_latency"
                    if measurement.latency_ms > self.settings.latency_threshold_ms:
                        incident, created = await open_incident(
                            session,
                            device_id=device_id,
                            kind=kind,
                            severity="warning",
                            deduplication_key=f"{device_id}:{kind}",
                            facts={
                                "check_type": check_key,
                                "latency_ms": measurement.latency_ms,
                                "threshold_ms": self.settings.latency_threshold_ms,
                            },
                            measurement_id=measurement.id,
                        )
                        if created:
                            events.append(self._incident_event("incident.created", incident))
                    else:
                        recovered = await recover_incident(
                            session,
                            device_id=device_id,
                            kind=kind,
                            facts={"latency_ms": measurement.latency_ms},
                            measurement_id=measurement.id,
                            required_confirmations=self.settings.recovery_threshold,
                        )
                        if recovered:
                            events.append(self._incident_event("incident.recovered", recovered))

                if (
                    measurement.outcome == CheckStatus.SUCCESS
                    and measurement.packet_loss_percent is not None
                ):
                    kind = "high_packet_loss"
                    if (
                        measurement.packet_loss_percent
                        > self.settings.packet_loss_threshold_percent
                    ):
                        incident, created = await open_incident(
                            session,
                            device_id=device_id,
                            kind=kind,
                            severity="warning",
                            deduplication_key=f"{device_id}:{kind}",
                            facts={
                                "packet_loss_percent": measurement.packet_loss_percent,
                                "threshold_percent": self.settings.packet_loss_threshold_percent,
                            },
                            measurement_id=measurement.id,
                        )
                        if created:
                            events.append(self._incident_event("incident.created", incident))
                    else:
                        recovered = await recover_incident(
                            session,
                            device_id=device_id,
                            kind=kind,
                            facts={"packet_loss_percent": measurement.packet_loss_percent},
                            measurement_id=measurement.id,
                            required_confirmations=self.settings.recovery_threshold,
                        )
                        if recovered:
                            events.append(self._incident_event("incident.recovered", recovered))

            device.check_failures = check_failures
            if not device.enabled:
                device.state = DeviceState.PAUSED.value
                device.failure_count = 0
                device.recovery_count = 0
            elif not successful:
                device.failure_count += 1
                device.recovery_count = 0
                if device.failure_count >= self.settings.failure_threshold:
                    device.state = DeviceState.DOWN.value
                    incident, created = await open_incident(
                        session,
                        device_id=device_id,
                        kind="unavailable",
                        severity="critical",
                        deduplication_key=f"{device_id}:unavailable",
                        facts={
                            "consecutive_failed_cycles": device.failure_count,
                            "check_outcomes": [item.outcome for item in measurements],
                        },
                        measurement_id=measurements[-1].id if measurements else None,
                    )
                    if created:
                        events.append(self._incident_event("incident.created", incident))
                elif previous_state == DeviceState.UP.value:
                    device.state = DeviceState.DEGRADED.value
                else:
                    device.state = DeviceState.UNKNOWN.value
            else:
                device.failure_count = 0
                device.recovery_count += 1
                is_fully_successful = not failures
                next_state = (
                    DeviceState.UP.value
                    if is_fully_successful
                    else DeviceState.DEGRADED.value
                )
                recovery_confirmed = (
                    device.recovery_count >= self.settings.recovery_threshold
                )
                if previous_state == DeviceState.DOWN.value and not recovery_confirmed:
                    device.state = DeviceState.DOWN.value
                else:
                    device.state = next_state
                    if recovery_confirmed:
                        recovered = await recover_incident(
                            session,
                            device_id=device_id,
                            kind="unavailable",
                            facts={
                                "recovery_confirmations": device.recovery_count,
                                "state": next_state,
                            },
                            measurement_id=measurements[-1].id,
                        )
                        if recovered:
                            events.append(self._incident_event("incident.recovered", recovered))

            await session.commit()

        for measurement in measurements:
            await self.broker.publish(
                {
                    "type": "measurement.created",
                    "device_id": device_id,
                    "measurement": self.measurement_dict(measurement),
                    "device_state": device.state,
                }
            )
        for event in events:
            await self.broker.publish(event)
        return measurements

    async def _recover_check_incident(
        self,
        session: AsyncSession,
        device: Device,
        measurement: Measurement,
        events: list[dict[str, Any]],
    ) -> None:
        recovered = await recover_incident(
            session,
            device_id=device.id,
            kind=f"{measurement.check_type}_failure",
            facts={"check_type": measurement.check_type, "outcome": "success"},
            measurement_id=measurement.id,
            required_confirmations=self.settings.recovery_threshold,
        )
        if recovered:
            events.append(self._incident_event("incident.recovered", recovered))

    @staticmethod
    async def _reset_check_recovery(
        session: AsyncSession,
        device_id: str,
        check_type: str,
    ) -> None:
        incident = await session.scalar(
            select(Incident).where(
                Incident.deduplication_key == f"{device_id}:{check_type}_failure",
                Incident.status == "active",
            )
        )
        if incident is not None:
            incident.observed_facts = {
                **incident.observed_facts,
                "recovery_confirmations": 0,
            }

    @staticmethod
    def measurement_dict(measurement: Measurement) -> dict[str, Any]:
        return {
            "id": measurement.id,
            "device_id": measurement.device_id,
            "check_type": measurement.check_type,
            "outcome": measurement.outcome,
            "started_at": measurement.started_at.isoformat(),
            "completed_at": measurement.completed_at.isoformat(),
            "latency_ms": measurement.latency_ms,
            "packet_loss_percent": measurement.packet_loss_percent,
            "details": measurement.details,
            "error": measurement.error,
        }

    @staticmethod
    def _incident_event(event_type: str, incident: Incident) -> dict[str, Any]:
        return {
            "type": event_type,
            "incident": {
                "id": incident.id,
                "device_id": incident.device_id,
                "kind": incident.kind,
                "severity": incident.severity,
                "status": incident.status,
                "started_at": incident.started_at.isoformat(),
                "recovered_at": incident.recovered_at.isoformat()
                if incident.recovered_at
                else None,
                "observed_facts": incident.observed_facts,
                "supporting_measurements": incident.supporting_measurements,
            },
        }


async def latest_measurement(
    session: AsyncSession,
    device_id: str,
) -> Measurement | None:
    return await session.scalar(
        select(Measurement)
        .where(Measurement.device_id == device_id)
        .order_by(Measurement.completed_at.desc())
        .limit(1)
    )
