from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from netpulse.models import Device, Measurement
from netpulse.schemas.devices import (
    CheckType,
    DeviceCreate,
    DeviceDetailResponse,
    DeviceListResponse,
    DevicePatch,
    DeviceResponse,
    DeviceState,
)
from netpulse.schemas.monitoring import CheckRequest
from netpulse.api.security import AdminRequired, visible_demo_hosts
from netpulse.services.monitoring import MonitoringService

router = APIRouter(prefix="/devices", tags=["devices"])


def _session(request: Request) -> AsyncSession:
    return request.app.state.sessions()


async def serialize_device(
    session: AsyncSession,
    device: Device,
    stale_after_seconds: int,
) -> DeviceResponse:
    measurement = await session.scalar(
        select(Measurement)
        .where(Measurement.device_id == device.id)
        .order_by(Measurement.completed_at.desc())
        .limit(1)
    )
    state = DeviceState.PAUSED if not device.enabled else DeviceState(device.state)
    checked_at = device.last_checked_at
    if device.enabled and checked_at is not None:
        normalized = checked_at.replace(tzinfo=timezone.utc) if checked_at.tzinfo is None else checked_at
        if (datetime.now(timezone.utc) - normalized).total_seconds() > stale_after_seconds:
            state = DeviceState.UNKNOWN
    latest = None
    if measurement is not None:
        latest = {
            "id": measurement.id,
            "check_type": measurement.check_type,
            "outcome": measurement.outcome,
            "completed_at": measurement.completed_at,
            "latency_ms": measurement.latency_ms,
            "packet_loss_percent": measurement.packet_loss_percent,
        }
    return DeviceResponse(
        id=device.id,
        name=device.name,
        hostname=device.hostname,
        device_type=device.device_type,
        description=device.description,
        tags=device.tags,
        enabled=device.enabled,
        interval_seconds=device.interval_seconds,
        check_types=device.check_types,
        ping_count=device.ping_count,
        check_timeout_seconds=device.check_timeout_seconds,
        tcp_port=device.tcp_port,
        dns_record_type=device.dns_record_type,
        state=state,
        failure_count=device.failure_count,
        recovery_count=device.recovery_count,
        created_at=device.created_at,
        updated_at=device.updated_at,
        last_checked_at=device.last_checked_at,
        latest_measurement=latest,
    )


async def get_device_or_404(
    session: AsyncSession,
    device_id: str,
    *,
    allowed_hosts: frozenset[str] | None = None,
) -> Device:
    device = await session.get(Device, device_id)
    if device is None or (
        allowed_hosts is not None and device.hostname not in allowed_hosts
    ):
        raise HTTPException(
            status_code=404,
            detail={"code": "device_not_found", "message": "Device was not found."},
        )
    return device


@router.get("", response_model=DeviceListResponse)
async def list_devices(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=120),
    state: DeviceState | None = None,
    enabled: bool | None = None,
    sort: str = Query(default="name", pattern=r"^(name|hostname|state|last_checked_at)$"),
    order: str = Query(default="asc", pattern=r"^(asc|desc)$"),
) -> DeviceListResponse:
    async with request.app.state.sessions() as session:
        query = select(Device)
        filters = []
        allowed_hosts = visible_demo_hosts(request)
        if allowed_hosts is not None:
            filters.append(Device.hostname.in_(allowed_hosts))
        if search:
            term = f"%{search.strip()}%"
            filters.append(or_(Device.name.ilike(term), Device.hostname.ilike(term)))
        if state is not None:
            if state is DeviceState.PAUSED:
                filters.append(Device.enabled.is_(False))
            else:
                filters.extend((Device.enabled.is_(True), Device.state == state.value))
        if enabled is not None:
            filters.append(Device.enabled.is_(enabled))
        if filters:
            query = query.where(*filters)
        total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
        sort_column = {
            "name": Device.name,
            "hostname": Device.hostname,
            "state": Device.state,
            "last_checked_at": Device.last_checked_at,
        }[sort]
        query = query.order_by(sort_column.desc() if order == "desc" else sort_column.asc())
        devices = (
            await session.scalars(query.offset((page - 1) * page_size).limit(page_size))
        ).all()
        items = [
            await serialize_device(
                session,
                device,
                request.app.state.settings.stale_after_seconds,
            )
            for device in devices
        ]
    return DeviceListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "",
    response_model=DeviceDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminRequired],
)
async def create_device(payload: DeviceCreate, request: Request) -> DeviceDetailResponse:
    async with request.app.state.sessions() as session:
        allowed_hosts = visible_demo_hosts(request)
        if allowed_hosts is not None:
            if payload.hostname not in allowed_hosts:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "demo_target_not_allowed",
                        "message": "Public demo devices may only target google.com or 8.8.8.8.",
                    },
                )
            duplicate = await session.scalar(
                select(Device.id).where(Device.hostname == payload.hostname).limit(1)
            )
            if duplicate is not None:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "demo_target_exists",
                        "message": "The public demo target is already configured.",
                    },
                )
        current_count = await session.scalar(select(func.count()).select_from(Device)) or 0
        if current_count >= request.app.state.settings.max_devices:
            raise HTTPException(
                status_code=409,
                detail={"code": "device_limit_reached", "message": "Maximum device count reached."},
            )
        now = datetime.now(timezone.utc)
        device = Device(
            **payload.model_dump(mode="json", exclude={"check_types"}),
            check_types=[check.value for check in payload.check_types],
            state=DeviceState.UNKNOWN.value,
            created_at=now,
            updated_at=now,
        )
        session.add(device)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail={"code": "device_conflict", "message": "Device could not be created."},
            ) from exc
        await session.refresh(device)
        response = await serialize_device(
            session, device, request.app.state.settings.stale_after_seconds
        )
    await request.app.state.broker.publish(
        {"type": "device.updated", "device": response.model_dump(mode="json")}
    )
    return response


@router.get("/{device_id}", response_model=DeviceDetailResponse)
async def get_device(device_id: str, request: Request) -> DeviceDetailResponse:
    async with request.app.state.sessions() as session:
        device = await get_device_or_404(
            session,
            device_id,
            allowed_hosts=visible_demo_hosts(request),
        )
        return await serialize_device(
            session, device, request.app.state.settings.stale_after_seconds
        )


@router.patch(
    "/{device_id}",
    response_model=DeviceDetailResponse,
    dependencies=[AdminRequired],
)
async def update_device(
    device_id: str,
    payload: DevicePatch,
    request: Request,
) -> DeviceDetailResponse:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=422,
            detail={"code": "empty_patch", "message": "At least one field must be provided."},
        )
    async with request.app.state.sessions() as session:
        device = await get_device_or_404(
            session,
            device_id,
            allowed_hosts=visible_demo_hosts(request),
        )
        allowed_hosts = visible_demo_hosts(request)
        if (
            allowed_hosts is not None
            and changes.get("hostname", device.hostname) not in allowed_hosts
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "demo_target_not_allowed",
                    "message": "Public demo devices may only target google.com or 8.8.8.8.",
                },
            )
        proposed_checks = [
            item.value if isinstance(item, CheckType) else item
            for item in changes.get("check_types", device.check_types)
        ]
        proposed_port = changes.get("tcp_port", device.tcp_port)
        if ("tcp" in proposed_checks) != (proposed_port is not None):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_check_configuration",
                    "message": "TCP monitoring requires tcp_port; remove tcp_port when TCP is disabled.",
                },
            )
        if "check_types" in changes:
            changes["check_types"] = proposed_checks
        for field, value in changes.items():
            setattr(device, field, value)
        if "enabled" in changes:
            if device.enabled:
                device.state = DeviceState.UNKNOWN.value
                device.failure_count = 0
                device.recovery_count = 0
            else:
                device.state = DeviceState.PAUSED.value
        device.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(device)
        response = await serialize_device(
            session, device, request.app.state.settings.stale_after_seconds
        )
    await request.app.state.broker.publish(
        {"type": "device.updated", "device": response.model_dump(mode="json")}
    )
    return response


@router.delete(
    "/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[AdminRequired],
)
async def delete_device(device_id: str, request: Request) -> None:
    async with request.app.state.sessions() as session:
        device = await get_device_or_404(
            session,
            device_id,
            allowed_hosts=visible_demo_hosts(request),
        )
        await session.delete(device)
        await session.commit()
    await request.app.state.broker.publish(
        {"type": "device.deleted", "device_id": device_id}
    )


@router.post("/{device_id}/check", dependencies=[AdminRequired])
async def manual_check(
    device_id: str,
    request: Request,
    payload: CheckRequest = CheckRequest(),
) -> dict:
    try:
        results = await request.app.state.monitoring.run_device(
            device_id,
            timeout_seconds=payload.timeout_seconds,
            ping_count=payload.ping_count,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "device_not_found", "message": str(exc)},
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "device_paused", "message": str(exc)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "check_in_progress", "message": str(exc)},
        ) from exc
    return {
        "device_id": device_id,
        "measurements": [
            request.app.state.monitoring.measurement_dict(item) for item in results
        ],
    }


@router.post(
    "/{device_id}/pause",
    response_model=DeviceDetailResponse,
    dependencies=[AdminRequired],
)
async def pause_device(device_id: str, request: Request) -> DeviceDetailResponse:
    return await update_device(
        device_id,
        DevicePatch(enabled=False),
        request,
    )


@router.post(
    "/{device_id}/resume",
    response_model=DeviceDetailResponse,
    dependencies=[AdminRequired],
)
async def resume_device(device_id: str, request: Request) -> DeviceDetailResponse:
    return await update_device(
        device_id,
        DevicePatch(enabled=True),
        request,
    )
