from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class CheckStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    DNS_ERROR = "dns_error"
    REFUSED = "refused"
    PROCESS_ERROR = "process_error"


@dataclass(frozen=True, slots=True)
class CheckResult:
    check_type: str
    status: CheckStatus
    started_at: datetime
    completed_at: datetime
    latency_ms: float | None = None
    packet_loss_percent: float | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def create(
        cls,
        check_type: str,
        status: CheckStatus,
        started_at: datetime,
        *,
        latency_ms: float | None = None,
        packet_loss_percent: float | None = None,
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> "CheckResult":
        return cls(
            check_type=check_type,
            status=status,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            latency_ms=latency_ms,
            packet_loss_percent=packet_loss_percent,
            details=details or {},
            error=error,
        )
