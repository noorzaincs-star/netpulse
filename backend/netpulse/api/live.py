import asyncio
import ipaddress
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def live_updates(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    allowed_origins = websocket.app.state.settings.cors_origins
    if origin is not None and origin not in allowed_origins:
        await websocket.close(code=1008, reason="Origin is not allowed.")
        return

    client = websocket.client.host if websocket.client else ""
    try:
        is_loopback = ipaddress.ip_address(client).is_loopback
    except ValueError:
        is_loopback = client in {"testclient", "localhost"}
    if not is_loopback and (origin is None or origin not in allowed_origins):
        await websocket.close(code=1008, reason="Origin is required for remote live updates.")
        return

    broker = websocket.app.state.broker
    queue = await broker.connect(websocket)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=20)
                await websocket.send_json(event)
            except TimeoutError:
                await websocket.send_json({"type": "keepalive"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket event client disconnected unexpectedly")
    finally:
        broker.disconnect(websocket)
