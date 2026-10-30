from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from netpulse.checks.validation import normalize_host


class DeviceState(StrEnum):
    UP = "UP"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"
    PAUSED = "PAUSED"


class CheckType(StrEnum):
    ICMP = "icmp"
    TCP = "tcp"
    DNS = "dns"


class DeviceBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    hostname: str = Field(min_length=1, max_length=253)
    device_type: str = Field(default="other", min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    enabled: bool = True
    interval_seconds: int = Field(default=60, ge=10, le=3600)
    check_types: list[CheckType] = Field(min_length=1, max_length=3)
    ping_count: int = Field(default=3, ge=1, le=10)
    check_timeout_seconds: float = Field(default=3.0, ge=0.1, le=30)
    tcp_port: int | None = Field(default=None, ge=1, le=65535)
    dns_record_type: str = Field(default="A", pattern=r"^(A|AAAA|CNAME|MX|NS|PTR|SOA|SRV|TXT)$")

    @field_validator("name", "device_type", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("hostname")
    @classmethod
    def normalize_hostname(cls, value: str) -> str:
        return normalize_host(value)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        cleaned = [tag.strip() for tag in value]
        if any(not tag or len(tag) > 40 for tag in cleaned):
            raise ValueError("Tags must contain 1 to 40 non-whitespace characters.")
        if len(set(tag.casefold() for tag in cleaned)) != len(cleaned):
            raise ValueError("Tags must be unique.")
        return cleaned

    @field_validator("check_types")
    @classmethod
    def unique_checks(cls, value: list[CheckType]) -> list[CheckType]:
        if len(set(value)) != len(value):
            raise ValueError("Check types must be unique.")
        return value

    @model_validator(mode="after")
    def validate_check_options(self) -> "DeviceBase":
        if CheckType.TCP in self.check_types and self.tcp_port is None:
            raise ValueError("tcp_port is required when TCP monitoring is configured.")
        if CheckType.TCP not in self.check_types and self.tcp_port is not None:
            raise ValueError("tcp_port is only allowed when TCP monitoring is configured.")
        return self


class DeviceCreate(DeviceBase):
    pass


class DevicePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    hostname: str | None = Field(default=None, min_length=1, max_length=253)
    device_type: str | None = Field(default=None, min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=1000)
    tags: list[str] | None = Field(default=None, max_length=20)
    enabled: bool | None = None
    interval_seconds: int | None = Field(default=None, ge=10, le=3600)
    check_types: list[CheckType] | None = Field(default=None, min_length=1, max_length=3)
    ping_count: int | None = Field(default=None, ge=1, le=10)
    check_timeout_seconds: float | None = Field(default=None, ge=0.1, le=30)
    tcp_port: int | None = Field(default=None, ge=1, le=65535)
    dns_record_type: str | None = Field(
        default=None, pattern=r"^(A|AAAA|CNAME|MX|NS|PTR|SOA|SRV|TXT)$"
    )

    @field_validator("name", "device_type", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("hostname")
    @classmethod
    def normalize_hostname(cls, value: str | None) -> str | None:
        return normalize_host(value) if value is not None else None

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [tag.strip() for tag in value]
        if any(not tag or len(tag) > 40 for tag in cleaned):
            raise ValueError("Tags must contain 1 to 40 non-whitespace characters.")
        if len(set(tag.casefold() for tag in cleaned)) != len(cleaned):
            raise ValueError("Tags must be unique.")
        return cleaned

    @field_validator("check_types")
    @classmethod
    def unique_checks(cls, value: list[CheckType] | None) -> list[CheckType] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("Check types must be unique.")
        return value

    @model_validator(mode="after")
    def reject_null_for_required_fields(self) -> "DevicePatch":
        required_fields = (
            "name",
            "hostname",
            "device_type",
            "enabled",
            "interval_seconds",
            "check_types",
            "ping_count",
            "check_timeout_seconds",
            "dns_record_type",
            "tags",
        )
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in required_fields
        ):
            raise ValueError("Required device fields cannot be null.")
        return self


class DeviceResponse(BaseModel):
    id: str
    name: str
    hostname: str
    device_type: str
    description: str | None
    tags: list[str]
    enabled: bool
    interval_seconds: int
    check_types: list[str]
    ping_count: int
    check_timeout_seconds: float
    tcp_port: int | None
    dns_record_type: str
    state: DeviceState
    failure_count: int
    recovery_count: int
    created_at: datetime
    updated_at: datetime
    last_checked_at: datetime | None
    latest_measurement: dict[str, Any] | None = None


class DeviceListResponse(BaseModel):
    items: list[DeviceResponse]
    total: int
    page: int
    page_size: int


class DeviceDetailResponse(DeviceResponse):
    pass
