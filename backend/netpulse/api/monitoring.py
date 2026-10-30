import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
import psutil
from sqlalchemy import func, select

from netpulse.api.devices import get_device_or_404
from netpulse.models import Device, Incident, Measurement, TopologyLink
from netpulse.schemas.devices import DeviceState
from netpulse.schemas.monitoring import (
    IncidentListResponse,
    IncidentResponse,
    MeasurementListResponse,
    MeasurementResponse,
    TopologyLinkCreate,
    TopologyLinkResponse,
    TopologyResponse,
)

router = APIRouter(tags=["monitoring"])


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@router.get("/measurements", response_model=MeasurementListResponse)
async def list_measurements(
    request: Request,
    device_id: str | None = None,
    check_type: str | None = Query(default=None, pattern=r"^(icmp|tcp|dns)$"),
    since: datetime | None = None,
    until: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> MeasurementListResponse:
    if since and until and _utc(since) > _utc(until):
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_date_range", "message": "since must be earlier than until."},
        )
    async with request.app.state.sessions() as session:
        query = select(Measurement)
        filters = []
        if device_id:
            filters.append(Measurement.device_id == device_id)
        if check_type:
            filters.append(Measurement.check_type == check_type)
        if since:
            filters.append(Measurement.completed_at >= _utc(since))
        if until:
            filters.append(Measurement.completed_at <= _utc(until))
        if filters:
            query = query.where(*filters)
        total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = (
            await session.scalars(
                query.order_by(Measurement.completed_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    return MeasurementListResponse(
        items=[MeasurementResponse.model_validate(item, from_attributes=True) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/devices/{device_id}/measurements", response_model=MeasurementListResponse)
async def list_device_measurements(
    device_id: str,
    request: Request,
    check_type: str | None = Query(default=None, pattern=r"^(icmp|tcp|dns)$"),
    since: datetime | None = None,
    until: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> MeasurementListResponse:
    async with request.app.state.sessions() as session:
        await get_device_or_404(session, device_id)
    return await list_measurements(
        request,
        device_id=device_id,
        check_type=check_type,
        since=since,
        until=until,
        page=page,
        page_size=page_size,
    )


@router.get("/incidents", response_model=IncidentListResponse)
async def list_incidents(
    request: Request,
    device_id: str | None = None,
    severity: str | None = Query(default=None, pattern=r"^(info|warning|critical)$"),
    incident_status: str | None = Query(default=None, alias="status", pattern=r"^(active|recovered)$"),
    since: datetime | None = None,
    until: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> IncidentListResponse:
    if since and until and _utc(since) > _utc(until):
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_date_range", "message": "since must be earlier than until."},
        )
    async with request.app.state.sessions() as session:
        query = select(Incident)
        filters = []
        if device_id:
            filters.append(Incident.device_id == device_id)
        if severity:
            filters.append(Incident.severity == severity)
        if incident_status:
            filters.append(Incident.status == incident_status)
        if since:
            filters.append(Incident.started_at >= _utc(since))
        if until:
            filters.append(Incident.started_at <= _utc(until))
        if filters:
            query = query.where(*filters)
        total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
        incidents = (
            await session.scalars(
                query.order_by(Incident.started_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    now = datetime.now(timezone.utc)
    responses = []
    for incident in incidents:
        started = _utc(incident.started_at)
        ended = _utc(incident.recovered_at) if incident.recovered_at else now
        responses.append(
            IncidentResponse(
                id=incident.id,
                device_id=incident.device_id,
                kind=incident.kind,
                severity=incident.severity,
                status=incident.status,
                started_at=incident.started_at,
                recovered_at=incident.recovered_at,
                duration_seconds=max(0.0, (ended - started).total_seconds()),
                observed_facts=incident.observed_facts,
                supporting_measurements=incident.supporting_measurements,
            )
        )
    return IncidentListResponse(
        items=responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/interfaces")
async def interfaces(request: Request) -> dict:
    try:
        return await asyncio.to_thread(request.app.state.interface_sampler.snapshot)
    except (OSError, psutil.Error) as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "interface_data_unavailable", "message": str(exc)},
        ) from exc


@router.get("/topology", response_model=TopologyResponse)
async def topology(request: Request) -> TopologyResponse:
    async with request.app.state.sessions() as session:
        devices = (await session.scalars(select(Device).order_by(Device.name))).all()
        links = (await session.scalars(select(TopologyLink))).all()
    return TopologyResponse(
        nodes=[
            {
                "id": device.id,
                "name": device.name,
                "hostname": device.hostname,
                "device_type": device.device_type,
                "state": DeviceState.PAUSED.value if not device.enabled else device.state,
                "enabled": device.enabled,
            }
            for device in devices
        ],
        links=[TopologyLinkResponse.model_validate(link, from_attributes=True) for link in links],
        relationships_note="Only manually configured links are shown. Checks do not reveal physical topology.",
    )


@router.post("/topology/links", response_model=TopologyLinkResponse, status_code=201)
async def create_topology_link(
    payload: TopologyLinkCreate,
    request: Request,
) -> TopologyLinkResponse:
    if payload.source_device_id == payload.target_device_id:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_topology_link", "message": "A device cannot link to itself."},
        )
    async with request.app.state.sessions() as session:
        for device_id in (payload.source_device_id, payload.target_device_id):
            await get_device_or_404(session, device_id)
        link = TopologyLink(
            source_device_id=payload.source_device_id,
            target_device_id=payload.target_device_id,
            label=payload.label.strip() if payload.label else None,
            created_at=datetime.now(timezone.utc),
        )
        session.add(link)
        await session.commit()
        await session.refresh(link)
        response = TopologyLinkResponse.model_validate(link, from_attributes=True)
    await request.app.state.broker.publish(
        {"type": "topology.updated", "link": response.model_dump(mode="json")}
    )
    return response


@router.delete("/topology/links/{link_id}", status_code=204)
async def delete_topology_link(link_id: str, request: Request) -> None:
    async with request.app.state.sessions() as session:
        link = await session.get(TopologyLink, link_id)
        if link is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "topology_link_not_found", "message": "Topology link was not found."},
            )
        await session.delete(link)
        await session.commit()
    await request.app.state.broker.publish(
        {"type": "topology.updated", "deleted_link_id": link_id}
    )


@router.get("/settings")
async def get_settings(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "limits": {
            "max_devices": settings.max_devices,
            "max_concurrency": settings.max_concurrency,
            "min_interval_seconds": 10,
            "max_interval_seconds": 3600,
            "max_page_size": 200,
        },
        "policy": {
            "failure_threshold": settings.failure_threshold,
            "recovery_threshold": settings.recovery_threshold,
            "stale_after_seconds": settings.stale_after_seconds,
            "latency_threshold_ms": settings.latency_threshold_ms,
            "packet_loss_threshold_percent": settings.packet_loss_threshold_percent,
            "measurement_retention_days": settings.measurement_retention_days,
        },
        "network_scope": "Explicitly configured targets only",
    }
