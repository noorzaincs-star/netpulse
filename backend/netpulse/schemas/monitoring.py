from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MeasurementResponse(BaseModel):
    id: str
    device_id: str
    check_type: str
    outcome: str
    started_at: datetime
    completed_at: datetime
    latency_ms: float | None
    packet_loss_percent: float | None
    details: dict[str, Any]
    error: str | None


class MeasurementListResponse(BaseModel):
    items: list[MeasurementResponse]
    total: int
    page: int
    page_size: int


class IncidentResponse(BaseModel):
    id: str
    device_id: str | None
    kind: str
    severity: str
    status: str
    started_at: datetime
    recovered_at: datetime | None
    duration_seconds: float | None = None
    observed_facts: dict[str, Any]
    supporting_measurements: list[str]


class IncidentListResponse(BaseModel):
    items: list[IncidentResponse]
    total: int
    page: int
    page_size: int


class CheckRequest(BaseModel):
    timeout_seconds: float | None = Field(default=None, ge=0.1, le=30)
    ping_count: int | None = Field(default=None, ge=1, le=10)


class TopologyLinkCreate(BaseModel):
    source_device_id: str
    target_device_id: str
    label: str | None = Field(default=None, max_length=120)


class TopologyLinkResponse(BaseModel):
    id: str
    source_device_id: str
    target_device_id: str
    label: str | None
    created_at: datetime


class TopologyResponse(BaseModel):
    nodes: list[dict[str, Any]]
    links: list[TopologyLinkResponse]
    relationships_note: str
