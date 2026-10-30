# API reference

The FastAPI application serves generated OpenAPI at `/openapi.json` and Swagger UI at `/docs`. All application routes use the `/api` prefix. HTTP validation and application errors use:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": []
  }
}
```

List routes return `items`, `total`, `page`, and `page_size`. Page size is bounded. Datetimes are UTC; measurement and incident `since`/`until` filters are inclusive and reject reversed ranges.

## Health

### `GET /api/health`

Returns process and database availability; it does not probe a target.

```json
{"status":"ok","database":"ok","version":"0.1.0"}
```

Database failures return HTTP 503.

## Devices

### `GET /api/devices`

Query options: `page` (1-based), `page_size` (1–100), `search`, `state`, `enabled`, `sort` (`name`, `hostname`, `state`, `last_checked_at`), and `order` (`asc`, `desc`).

### `POST /api/devices`

Creates an explicitly configured target (HTTP 201). Fields include `name`, `hostname`, `device_type`, optional `description`, `tags`, `enabled`, `interval_seconds` (10–3600), `check_types` (`icmp`, `tcp`, `dns`), `ping_count` (1–10), `check_timeout_seconds` (0.1–30), optional `tcp_port` (required exactly when TCP is enabled), and `dns_record_type`.

Example:

```json
{
  "name": "Office gateway",
  "hostname": "192.168.1.1",
  "device_type": "router",
  "interval_seconds": 60,
  "check_types": ["icmp", "tcp"],
  "ping_count": 3,
  "check_timeout_seconds": 3,
  "tcp_port": 443
}
```

### `GET /api/devices/{device_id}`

Returns configuration, current state, failure/recovery counters, last check, and latest measurement summary. Stale enabled devices are presented as `UNKNOWN`.

### `PATCH /api/devices/{device_id}`

Updates supplied device fields; empty patches and invalid check configurations return HTTP 422.

### `DELETE /api/devices/{device_id}`

Deletes the device (HTTP 204); SQLite foreign-key rules remove measurements and topology edges and preserve incident history with a null device reference.

### `POST /api/devices/{device_id}/check`

Runs configured checks now and returns their persisted measurements. Optional JSON `timeout_seconds` and `ping_count` override that device's configured values for this run. Paused devices return 409; a missing device returns 404; duplicate concurrent checks return 409. This is a bounded synchronous request, not a queued job.

### `POST /api/devices/{device_id}/pause` and `/resume`

Pause or resume scheduled checks and return the updated device.

## Measurements and incidents

### `GET /api/measurements`

Supports `device_id`, `check_type`, `since`, `until`, `page`, and `page_size` (1–200).

### `GET /api/devices/{device_id}/measurements`

Returns the same bounded, date-filterable history for one existing device.

### `GET /api/incidents`

Supports `device_id`, `severity` (`info`, `warning`, `critical`), `status` (`active`, `recovered`), `since`, `until`, `page`, and `page_size` (1–200). Active incident duration is computed at response time. Repeated active incidents deduplicate by device and kind.

## Local interfaces, topology, and settings

- `GET /api/interfaces`: current local-host psutil interface counters, state, and rates. A first sample has no rate; counters are never represented as per-device bandwidth.
- `GET /api/topology`: registered devices plus manually configured links and an explicit note that physical relationships are not inferred.
- `POST /api/topology/links`: create a link with `source_device_id`, `target_device_id`, and optional `label`. Self-links and unknown device IDs are rejected.
- `DELETE /api/topology/links/{link_id}`: remove a manual link (HTTP 204).
- `GET /api/settings`: non-secret limits and effective monitoring thresholds.

## WebSocket

### `WS /api/ws`

Streams committed `device.updated`, `device.deleted`, `measurement.created`, `incident.created`, `incident.recovered`, and topology updates. A keepalive is sent during idle periods. Connections are loopback-only; browser `Origin` must match configured CORS origins. The frontend reconnects with backoff and continues REST polling while disconnected.
