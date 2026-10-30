import dns.exception
import dns.resolver
import pytest

from netpulse.checks.dns import query_dns
from netpulse.checks.result import CheckStatus


class FakeRecord:
    def to_text(self) -> str:
        return "192.0.2.8"


class FakeResolver:
    nameservers = ["192.0.2.53"]
    timeout = 0.0
    lifetime = 0.0
    outcome: list[FakeRecord] | Exception = [FakeRecord()]

    def __init__(self, *, configure: bool) -> None:
        assert configure is False

    async def resolve(
        self, name: str, record_type: int, *, lifetime: float
    ) -> list[FakeRecord]:
        assert name == "example.com"
        assert lifetime == 0.2
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.mark.asyncio
async def test_dns_success_returns_resolver_and_records(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dns.asyncresolver.Resolver", FakeResolver)
    result = await query_dns(
        "Example.COM",
        "A",
        timeout_seconds=0.2,
        nameservers=["192.0.2.53"],
    )

    assert result.status is CheckStatus.SUCCESS
    assert result.details["resolver"] == ["192.0.2.53"]
    assert result.details["records"] == ["192.0.2.8"]


@pytest.mark.asyncio
async def test_dns_nxdomain_is_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeResolver.outcome = dns.resolver.NXDOMAIN()
    monkeypatch.setattr("dns.asyncresolver.Resolver", FakeResolver)
    try:
        result = await query_dns(
            "example.com", timeout_seconds=0.2, nameservers=["192.0.2.53"]
        )
    finally:
        FakeResolver.outcome = [FakeRecord()]

    assert result.status is CheckStatus.DNS_ERROR
    assert "NXDOMAIN" in result.error


@pytest.mark.asyncio
async def test_dns_timeout_is_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeResolver.outcome = dns.exception.Timeout()
    monkeypatch.setattr("dns.asyncresolver.Resolver", FakeResolver)
    try:
        result = await query_dns(
            "example.com", timeout_seconds=0.2, nameservers=["192.0.2.53"]
        )
    finally:
        FakeResolver.outcome = [FakeRecord()]

    assert result.status is CheckStatus.TIMEOUT


@pytest.mark.asyncio
async def test_dns_rejects_unsupported_record_type() -> None:
    with pytest.raises(ValueError, match="Unsupported DNS record type"):
        await query_dns("example.com", "ANY")
