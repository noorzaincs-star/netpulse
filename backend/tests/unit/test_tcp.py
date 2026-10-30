import asyncio
import socket

import pytest

from netpulse.checks.result import CheckStatus
from netpulse.checks.tcp import check_tcp


class FakeWriter:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


@pytest.mark.asyncio
async def test_tcp_success_closes_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = FakeWriter()

    async def open_connection(host: str, port: int) -> tuple[object, FakeWriter]:
        assert (host, port) == ("127.0.0.1", 443)
        return object(), writer

    monkeypatch.setattr("asyncio.open_connection", open_connection)
    result = await check_tcp("127.0.0.1", 443)

    assert result.status is CheckStatus.SUCCESS
    assert result.latency_ms is not None
    assert writer.closed


@pytest.mark.asyncio
async def test_tcp_refusal_is_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    async def open_connection(host: str, port: int) -> tuple[object, object]:
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr("asyncio.open_connection", open_connection)
    result = await check_tcp("localhost", 9)

    assert result.status is CheckStatus.REFUSED
    assert result.latency_ms is None


@pytest.mark.asyncio
async def test_tcp_timeout_is_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    async def open_connection(host: str, port: int) -> tuple[object, object]:
        await asyncio.sleep(1)
        return object(), object()

    monkeypatch.setattr("asyncio.open_connection", open_connection)
    result = await check_tcp("localhost", 443, timeout_seconds=0.1)

    assert result.status is CheckStatus.TIMEOUT
