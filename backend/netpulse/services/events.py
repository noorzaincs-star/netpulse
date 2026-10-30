import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventBroker:
    def __init__(self, queue_size: int = 100) -> None:
        self._clients: dict[WebSocket, asyncio.Queue[dict[str, Any]]] = {}
        self._queue_size = queue_size

    async def connect(self, websocket: WebSocket) -> asyncio.Queue[dict[str, Any]]:
        await websocket.accept()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(self._queue_size)
        self._clients[websocket] = queue
        return queue

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.pop(websocket, None)

    async def publish(self, event: dict[str, Any]) -> None:
        for websocket, queue in tuple(self._clients.items()):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    logger.debug("WebSocket event queue emptied during overflow handling.")
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Dropping live event for a slow WebSocket client.")
