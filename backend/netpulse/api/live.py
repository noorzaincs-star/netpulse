import asyncio
import ipaddress
import logging
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from netpulse.core.config import PUBLIC_DEMO_TARGETS
from netpulse.models import Device

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def live_updates(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    allowed_origins = websocket.app.state.settings.cors_origins
    host = websocket.url.hostname or ""
    parsed_origin = urlsplit(origin) if origin is not None else None
    same_huggingface_origin = (
        websocket.app.state.settings.public_demo_mode
        and parsed_origin is not None
        and parsed_origin.scheme == "https"
        and parsed_origin.hostname == host
        and host.endswith(".hf.space")
    )
    if (
        origin is not None
        and origin not in allowed_origins
        and not same_huggingface_origin
    ):
        await websocket.close(code=1008, reason="Origin is not allowed.")
        return

    client = websocket.client.host if websocket.client else ""
    try:
        is_loopback = ipaddress.ip_address(client).is_loopback
    except ValueError:
        is_loopback = client in {"testclient", "localhost"}
    if not is_loopback and (
        origin is None
        or (origin not in allowed_origins and not same_huggingface_origin)
    ):
        await websocket.close(code=1008, reason="Origin is required for remote live updates.")
        return

    broker = websocket.app.state.broker
    queue = await broker.connect(websocket)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=20)
                if websocket.app.state.settings.public_demo_mode:
                    device_id = event.get("device_id")
                    incident = event.get("incident")
                    if device_id is None and isinstance(incident, dict):
                        device_id = incident.get("device_id")
                    device = event.get("device")
                    if isinstance(device, dict):
                        if device.get("hostname") not in PUBLIC_DEMO_TARGETS:
                            continue
                    elif device_id is not None:
                        async with websocket.app.state.sessions() as session:
                            is_demo_device = await session.scalar(
                                select(Device.id).where(
                                    Device.id == device_id,
                                    Device.hostname.in_(PUBLIC_DEMO_TARGETS),
                                )
                            )
                        if is_demo_device is None:
                            continue
                    elif event.get("type") == "topology.updated":
                        link = event.get("link")
                        if not isinstance(link, dict):
                            continue
                        async with websocket.app.state.sessions() as session:
                            allowed_ids = set(
                                (
                                    await session.scalars(
                                        select(Device.id).where(
                                            Device.id.in_(
                                                (
                                                    link.get("source_device_id"),
                                                    link.get("target_device_id"),
                                                )
                                            ),
                                            Device.hostname.in_(PUBLIC_DEMO_TARGETS),
                                        )
                                    )
                                ).all()
                            )
                        if allowed_ids != {
                            link.get("source_device_id"),
                            link.get("target_device_id"),
                        }:
                            continue
                    else:
                        continue
                await websocket.send_json(event)
            except TimeoutError:
                await websocket.send_json({"type": "keepalive"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket event client disconnected unexpectedly")
    finally:
        broker.disconnect(websocket)
