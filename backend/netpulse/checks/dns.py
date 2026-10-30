import time
import re
from datetime import datetime, timezone

import dns.asyncresolver
import dns.exception
import dns.resolver
from dns.rdatatype import from_text

from netpulse.checks.result import CheckResult, CheckStatus
from netpulse.checks.validation import normalize_host

_SUPPORTED_RECORD_TYPES = {"A", "AAAA", "CNAME", "MX", "NS", "PTR", "SOA", "SRV", "TXT"}
_SRV_LABEL = re.compile(r"^_[A-Za-z0-9-]{1,62}$")


def _normalize_query_name(name: str, record_type: str) -> str:
    if record_type != "SRV":
        return normalize_host(name)
    labels = name.rstrip(".").split(".")
    if len(labels) < 3 or not all(_SRV_LABEL.fullmatch(label) for label in labels[:2]):
        raise ValueError("SRV query names must begin with _service._protocol.")
    return ".".join(
        [labels[0].lower(), labels[1].lower(), normalize_host(".".join(labels[2:]))]
    )


async def query_dns(
    name: str,
    record_type: str = "A",
    *,
    timeout_seconds: float = 3.0,
    nameservers: list[str] | None = None,
) -> CheckResult:
    query_type = record_type.upper()
    if query_type not in _SUPPORTED_RECORD_TYPES:
        raise ValueError(f"Unsupported DNS record type: {record_type}.")
    query_name = _normalize_query_name(name, query_type)
    if not 0.1 <= timeout_seconds <= 30:
        raise ValueError("DNS timeout must be between 0.1 and 30 seconds.")

    resolver = dns.asyncresolver.Resolver(configure=nameservers is None)
    if nameservers is not None:
        resolver.nameservers = nameservers
    resolver.timeout = timeout_seconds
    resolver.lifetime = timeout_seconds
    started_at = datetime.now(timezone.utc)
    started_clock = time.monotonic()
    status = CheckStatus.SUCCESS
    error = None
    records: list[str] = []
    try:
        answer = await resolver.resolve(
            query_name,
            from_text(query_type),
            lifetime=timeout_seconds,
        )
        records = [record.to_text() for record in answer]
    except dns.resolver.NXDOMAIN as exc:
        status = CheckStatus.DNS_ERROR
        error = "DNS name does not exist (NXDOMAIN)."
    except dns.exception.Timeout:
        status = CheckStatus.TIMEOUT
        error = "DNS query timed out."
    except dns.resolver.NoNameservers:
        status = CheckStatus.DNS_ERROR
        error = "No configured DNS server returned a usable response."
    except dns.exception.DNSException as exc:
        status = CheckStatus.DNS_ERROR
        error = str(exc)

    return CheckResult.create(
        "dns",
        status,
        started_at,
        latency_ms=(time.monotonic() - started_clock) * 1000,
        details={
            "name": query_name,
            "record_type": query_type,
            "resolver": [str(server) for server in resolver.nameservers],
            "records": records,
        },
        error=error,
    )
