import asyncio

import pytest

from netpulse.checks.ping import ping_host
from netpulse.checks.result import CheckStatus


class FakeProcess:
    def __init__(self, returncode: int, output: bytes = b"") -> None:
        self.returncode = returncode
        self.output = output
        self.killed = False

    async def communicate(self) -> tuple[bytes, None]:
        return self.output, None

    def kill(self) -> None:
        self.killed = True


@pytest.mark.asyncio
async def test_ping_success_uses_safe_argument_list(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, ...]] = []

    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        calls.append(args)
        assert kwargs["stdout"] == asyncio.subprocess.PIPE
        assert kwargs["stderr"] == asyncio.subprocess.STDOUT
        return FakeProcess(0, b"Reply from 127.0.0.1: time=12ms")

    monkeypatch.setattr("netpulse.checks.ping._ping_executable", lambda: "ping.exe")
    monkeypatch.setattr("asyncio.create_subprocess_exec", create_process)
    result = await ping_host("127.0.0.1", count=2, timeout_seconds=0.2)

    assert result.status is CheckStatus.SUCCESS
    assert result.latency_ms == 12
    assert result.packet_loss_percent == 0
    assert result.details["completed_attempts"] == 2
    assert all(call[0] == "ping.exe" and "127.0.0.1" in call for call in calls)
    assert all("-n" in call and "1" in call for call in calls)


@pytest.mark.asyncio
async def test_ping_uses_ipv6_flag_for_ipv6_literals(monkeypatch: pytest.MonkeyPatch) -> None:
    call_args: list[object] = []

    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        call_args.extend(args)
        return FakeProcess(0, b"Reply from 2001:db8::1: time=1ms")

    monkeypatch.setattr("netpulse.checks.ping._ping_executable", lambda: "ping.exe")
    monkeypatch.setattr("asyncio.create_subprocess_exec", create_process)
    result = await ping_host("2001:db8::1", count=1)

    assert result.status is CheckStatus.SUCCESS
    assert "-6" in call_args


@pytest.mark.asyncio
async def test_ping_no_reply_counts_loss_from_completed_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        return FakeProcess(1, b"Request timed out.")

    monkeypatch.setattr("netpulse.checks.ping._ping_executable", lambda: "ping.exe")
    monkeypatch.setattr("asyncio.create_subprocess_exec", create_process)
    result = await ping_host("example.com", count=3, timeout_seconds=0.2)

    assert result.status is CheckStatus.FAILURE
    assert result.packet_loss_percent == 100
    assert result.details["replies"] == 0


@pytest.mark.asyncio
async def test_ping_timeout_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    class HungProcess(FakeProcess):
        calls = 0

        async def communicate(self) -> tuple[bytes, None]:
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError
            return b"", None

    process = HungProcess(1)

    async def create_process(*args: object, **kwargs: object) -> HungProcess:
        return process

    monkeypatch.setattr("netpulse.checks.ping._ping_executable", lambda: "ping.exe")
    monkeypatch.setattr("asyncio.create_subprocess_exec", create_process)
    result = await ping_host("127.0.0.1", count=1, timeout_seconds=0.1)

    assert process.killed
    assert result.status is CheckStatus.TIMEOUT
    assert result.packet_loss_percent == 100


@pytest.mark.asyncio
async def test_ping_cancellation_terminates_the_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HungProcess(FakeProcess):
        def __init__(self) -> None:
            super().__init__(1)
            self.started = asyncio.Event()

        async def communicate(self) -> tuple[bytes, None]:
            self.started.set()
            await asyncio.Future()

        async def wait(self) -> int:
            return 1

    process = HungProcess()

    async def create_process(*args: object, **kwargs: object) -> HungProcess:
        return process

    monkeypatch.setattr("netpulse.checks.ping._ping_executable", lambda: "ping.exe")
    monkeypatch.setattr("asyncio.create_subprocess_exec", create_process)
    task = asyncio.create_task(ping_host("127.0.0.1", count=1))
    await process.started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert process.killed


@pytest.mark.asyncio
async def test_ping_process_failure_does_not_inflate_packet_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        raise FileNotFoundError("ping.exe is unavailable")

    monkeypatch.setattr("netpulse.checks.ping._ping_executable", lambda: "ping.exe")
    monkeypatch.setattr("asyncio.create_subprocess_exec", create_process)
    result = await ping_host("127.0.0.1", count=2, timeout_seconds=0.1)

    assert result.status is CheckStatus.PROCESS_ERROR
    assert result.packet_loss_percent is None
