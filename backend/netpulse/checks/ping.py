import asyncio
import ipaddress
import re
import shutil
import sys
import time
from datetime import datetime, timezone

from netpulse.checks.result import CheckResult, CheckStatus
from netpulse.checks.validation import normalize_host

_LATENCY = re.compile(r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)


def _ping_executable() -> str:
    name = "ping.exe" if sys.platform == "win32" else "ping"
    return shutil.which(name) or name


async def ping_host(
    host: str,
    *,
    count: int = 4,
    timeout_seconds: float = 1.0,
) -> CheckResult:
    target = normalize_host(host)
    if not 1 <= count <= 10:
        raise ValueError("Ping count must be between 1 and 10.")
    if not 0.1 <= timeout_seconds <= 30:
        raise ValueError("Ping timeout must be between 0.1 and 30 seconds.")

    started_at = datetime.now(timezone.utc)
    started_clock = time.monotonic()
    executable = _ping_executable()
    address = None
    try:
        address = ipaddress.ip_address(target)
    except ValueError:
        pass

    replies = 0
    completed_attempts = 0
    latencies: list[float] = []
    process_errors: list[str] = []
    timeouts = 0

    for _ in range(count):
        if sys.platform == "win32":
            args = ["-n", "1", "-w", str(max(1, round(timeout_seconds * 1000)))]
        else:
            args = ["-c", "1", "-W", str(max(1, round(timeout_seconds)))]
        if address is not None and address.version == 6:
            args.insert(0, "-6")
        args.append(target)
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                output, _ = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_seconds + 1.0,
                )
            except TimeoutError:
                process.kill()
                await process.communicate()
                timeouts += 1
                completed_attempts += 1
                continue
            except asyncio.CancelledError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
                raise
        except OSError as exc:
            process_errors.append(str(exc))
            break

        completed_attempts += 1
        if process.returncode == 0:
            replies += 1
            match = _LATENCY.search(output.decode(errors="replace"))
            if match:
                latencies.append(float(match.group(1)))

    loss = (
        ((completed_attempts - replies) / completed_attempts) * 100
        if completed_attempts
        else None
    )
    if process_errors:
        status = CheckStatus.PROCESS_ERROR
    elif replies:
        status = CheckStatus.SUCCESS
    elif timeouts == count:
        status = CheckStatus.TIMEOUT
    else:
        status = CheckStatus.FAILURE

    return CheckResult.create(
        "icmp",
        status,
        started_at,
        latency_ms=sum(latencies) / len(latencies) if latencies else None,
        packet_loss_percent=loss,
        details={
            "target": target,
            "attempts": count,
            "completed_attempts": completed_attempts,
            "replies": replies,
            "timeouts": timeouts,
            "elapsed_ms": (time.monotonic() - started_clock) * 1000,
        },
        error=process_errors[0] if process_errors else None,
    )
