import asyncio
import socket
import time
from datetime import datetime, timezone

from netpulse.checks.result import CheckResult, CheckStatus
from netpulse.checks.validation import normalize_host


async def check_tcp(
    host: str,
    port: int,
    *,
    timeout_seconds: float = 3.0,
) -> CheckResult:
    target = normalize_host(host)
    if not 1 <= port <= 65535:
        raise ValueError("TCP port must be between 1 and 65535.")
    if not 0.1 <= timeout_seconds <= 30:
        raise ValueError("TCP timeout must be between 0.1 and 30 seconds.")

    started_at = datetime.now(timezone.utc)
    started_clock = time.monotonic()
    writer: asyncio.StreamWriter | None = None
    status = CheckStatus.SUCCESS
    error = None
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(target, port),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        status = CheckStatus.TIMEOUT
        error = "TCP connection timed out."
    except ConnectionRefusedError:
        status = CheckStatus.REFUSED
        error = "TCP connection was refused."
    except socket.gaierror as exc:
        status = CheckStatus.DNS_ERROR
        error = str(exc)
    except OSError as exc:
        status = CheckStatus.FAILURE
        error = str(exc)
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    return CheckResult.create(
        "tcp",
        status,
        started_at,
        latency_ms=(time.monotonic() - started_clock) * 1000
        if status is CheckStatus.SUCCESS
        else None,
        details={"host": target, "port": port},
        error=error,
    )
