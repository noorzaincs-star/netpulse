import os
from dataclasses import dataclass
from math import isfinite
from urllib.parse import urlsplit

from dotenv import load_dotenv

PUBLIC_DEMO_TARGETS = frozenset({"google.com", "8.8.8.8"})


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = "sqlite+aiosqlite:///./netpulse.db"
    host: str = "127.0.0.1"
    port: int = 8000
    max_devices: int = 500
    max_concurrency: int = 32
    failure_threshold: int = 3
    recovery_threshold: int = 2
    stale_after_seconds: int = 180
    latency_threshold_ms: float = 250.0
    packet_loss_threshold_percent: float = 20.0
    measurement_retention_days: int = 30
    cors_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")
    public_demo_mode: bool = False
    admin_token: str | None = None
    allowed_hosts: tuple[str, ...] = (
        "localhost",
        "127.0.0.1",
        "::1",
    )

    def __post_init__(self) -> None:
        if not 1 <= self.max_devices <= 10_000:
            raise ValueError("max_devices must be between 1 and 10000.")
        if not 1 <= self.max_concurrency <= 256:
            raise ValueError("max_concurrency must be between 1 and 256.")
        if not 1 <= self.failure_threshold <= 100:
            raise ValueError("failure_threshold must be between 1 and 100.")
        if not 1 <= self.recovery_threshold <= 100:
            raise ValueError("recovery_threshold must be between 1 and 100.")
        if self.stale_after_seconds < 1:
            raise ValueError("stale_after_seconds must be positive.")
        if not isfinite(self.latency_threshold_ms) or self.latency_threshold_ms <= 0:
            raise ValueError("latency_threshold_ms must be a positive finite number.")
        if (
            not isfinite(self.packet_loss_threshold_percent)
            or not 0 <= self.packet_loss_threshold_percent <= 100
        ):
            raise ValueError("packet_loss_threshold_percent must be between 0 and 100.")
        if not 1 <= self.measurement_retention_days <= 3650:
            raise ValueError("measurement_retention_days must be between 1 and 3650.")
        for origin in self.cors_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or parsed.hostname is None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
            ):
                raise ValueError("CORS origins must be HTTP(S) origins without paths or credentials.")
        if any(not host or host != host.strip() for host in self.allowed_hosts):
            raise ValueError("allowed_hosts must contain non-empty hostnames.")
        if self.public_demo_mode and (
            self.admin_token is None
            or len(self.admin_token) < 32
            or not self.admin_token.strip()
        ):
            raise ValueError(
                "ADMIN_TOKEN must contain at least 32 characters when NETPULSE_DEMO is enabled."
            )

    @classmethod
    def from_environment(cls) -> "Settings":
        load_dotenv()
        origins = os.environ.get(
            "CORS_ORIGINS",
            os.environ.get(
                "NETPULSE_CORS_ORIGINS",
                "http://127.0.0.1:5173,http://localhost:5173",
            ),
        )
        render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
        configured_hosts = os.environ.get("NETPULSE_ALLOWED_HOSTS", "")
        public_demo_mode = os.environ.get("NETPULSE_DEMO", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        allowed_hosts = ("localhost", "127.0.0.1", "::1")
        allowed_hosts += tuple(
            host.strip().lower()
            for host in (render_hostname, *configured_hosts.split(","))
            if host.strip()
        )
        return cls(
            database_url=os.environ.get(
                "NETPULSE_DATABASE_URL",
                "sqlite+aiosqlite:///./netpulse.db",
            ),
            max_devices=int(os.environ.get("NETPULSE_MAX_DEVICES", "500")),
            max_concurrency=int(os.environ.get("NETPULSE_MAX_CONCURRENCY", "32")),
            failure_threshold=int(os.environ.get("NETPULSE_FAILURE_THRESHOLD", "3")),
            recovery_threshold=int(os.environ.get("NETPULSE_RECOVERY_THRESHOLD", "2")),
            stale_after_seconds=int(os.environ.get("NETPULSE_STALE_SECONDS", "180")),
            latency_threshold_ms=float(os.environ.get("NETPULSE_LATENCY_THRESHOLD_MS", "250")),
            packet_loss_threshold_percent=float(
                os.environ.get("NETPULSE_PACKET_LOSS_THRESHOLD_PERCENT", "20")
            ),
            measurement_retention_days=int(os.environ.get("NETPULSE_RETENTION_DAYS", "30")),
            cors_origins=tuple(origin.strip().rstrip("/") for origin in origins.split(",") if origin.strip()),
            allowed_hosts=tuple(dict.fromkeys(allowed_hosts)),
            public_demo_mode=public_demo_mode,
            admin_token=os.environ.get("ADMIN_TOKEN") or None,
        )
