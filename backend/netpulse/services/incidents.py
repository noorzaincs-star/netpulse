from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from netpulse.models import AlertEvent, Incident


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def open_incident(
    session: AsyncSession,
    *,
    device_id: str,
    kind: str,
    severity: str,
    deduplication_key: str,
    facts: dict[str, Any],
    measurement_id: str | None,
) -> tuple[Incident, bool]:
    existing = await session.scalar(
        select(Incident).where(
            Incident.deduplication_key == deduplication_key,
            Incident.status == "active",
        )
    )
    now = utc_now()
    if existing is not None:
        existing.observed_facts = facts
        existing.observed_facts["recovery_confirmations"] = 0
        if measurement_id and measurement_id not in existing.supporting_measurements:
            existing.supporting_measurements = [
                *existing.supporting_measurements,
                measurement_id,
            ]
        return existing, False

    incident = Incident(
        device_id=device_id,
        kind=kind,
        severity=severity,
        status="active",
        deduplication_key=deduplication_key,
        started_at=now,
        supporting_measurements=[measurement_id] if measurement_id else [],
        observed_facts=facts,
    )
    session.add(incident)
    await session.flush()
    session.add(
        AlertEvent(
            incident_id=incident.id,
            event_type="created",
            occurred_at=now,
            payload=facts,
        )
    )
    return incident, True


async def recover_incident(
    session: AsyncSession,
    *,
    device_id: str,
    kind: str,
    facts: dict[str, Any],
    measurement_id: str | None,
    required_confirmations: int = 1,
) -> Incident | None:
    key = f"{device_id}:{kind}"
    incident = await session.scalar(
        select(Incident).where(
            Incident.deduplication_key == key,
            Incident.status == "active",
        )
    )
    if incident is None:
        return None

    confirmations = int(incident.observed_facts.get("recovery_confirmations", 0)) + 1
    incident.observed_facts = {
        **incident.observed_facts,
        "recovery_confirmations": confirmations,
    }
    if confirmations < required_confirmations:
        return None

    now = utc_now()
    incident.status = "recovered"
    incident.recovered_at = now
    incident.observed_facts = {
        **incident.observed_facts,
        "recovery": facts,
    }
    if measurement_id and measurement_id not in incident.supporting_measurements:
        incident.supporting_measurements = [
            *incident.supporting_measurements,
            measurement_id,
        ]
    session.add(
        AlertEvent(
            incident_id=incident.id,
            event_type="recovered",
            occurred_at=now,
            payload=facts,
        )
    )
    return incident
