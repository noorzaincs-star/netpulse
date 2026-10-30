import asyncio

import pytest

from netpulse.checks.result import CheckStatus
from netpulse.checks.tcp import check_tcp


@pytest.mark.asyncio
async def test_tcp_check_against_explicit_localhost_target() -> None:
    server = await asyncio.start_server(
        lambda reader, writer: writer.close(),
        host="127.0.0.1",
        port=0,
    )
    port = server.sockets[0].getsockname()[1]
    try:
        result = await check_tcp("127.0.0.1", port, timeout_seconds=1)
    finally:
        server.close()
        await server.wait_closed()

    assert result.status is CheckStatus.SUCCESS
    assert result.details == {"host": "127.0.0.1", "port": port}
