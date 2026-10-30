# NetPulse implementation plan

## 1. Architecture

NetPulse will be a local-first, single-user application with two processes:

- A FastAPI service owns configuration, SQLite persistence, monitoring lifecycle, and network operations.
- A React/Vite client reads the service over localhost HTTP and WebSocket. REST polling remains available if a WebSocket disconnects.

The service separates transport/API concerns, validation and domain logic, network adapters, persistence, and scheduled work. Async SQLAlchemy sessions handle SQLite work outside network operations; the lifecycle-managed worker bounds network concurrency and batches retention deletes.

The browser will never perform network checks itself. A displayed measurement is sourced from a persisted backend result and includes its status and timestamp. Missing/stale results are shown as unavailable or stale, not replaced with sample values.

## 2. Current file structure

```text
backend/netpulse/
├── api/          # REST and WebSocket endpoints
├── checks/       # safe ping, TCP, DNS adapters and validation
├── core/         # settings
├── db/           # async engine, initialization and additive upgrade
├── models/       # SQLAlchemy entities
├── schemas/      # Pydantic request/response contracts
└── services/     # monitoring, incidents, worker, events, interfaces
backend/tests/
├── unit/
└── integration/
frontend/src/
├── app/          # dashboard and device details
├── components/   # device dialog and topology view
├── hooks/        # live connection and polling fallback
└── lib/          # REST/WebSocket client
docs/             # architecture, API, database, plan, incident example
```

The dashboard uses real API responses; no demo measurement fixture is used outside tests.

## 3. Data model

All stored datetimes will be UTC. Device IDs will be stable generated identifiers. Frequently filtered measurement and incident rows will be indexed by device and timestamp.

| Entity | Core fields and purpose |
|---|---|
| `Device` | ID, name, normalized hostname/IP, device type, description, tags, enabled flag, interval, check timeout, ping count, configured check definitions, created/updated timestamps |
| `Measurement` | ID, device ID, check type, outcome, start/completion time, latency, packet loss/attempt counts, resolver/record data or TCP endpoint as applicable, bounded error details |
| `Incident` | ID, optional device ID, kind, severity, status, start/recovery timestamps, deduplication key, observed facts, supporting measurement references |
| `AlertEvent` | ID, incident ID, event type, timestamp, and event payload for incident lifecycle history |
| `MonitoringConfig` | Singleton effective global limits, thresholds, stale duration, refresh/retention settings |
| `TopologyLink` | ID, source/target device IDs, manually configured relationship label and timestamps; no inferred physical relationship |

Measurements preserve per-check outcomes so a failed ICMP echo does not override a successful TCP check. Device state is derived from enabled checks and policy, with explicit `UP`, `DEGRADED`, `DOWN`, `UNKNOWN`, and `PAUSED` states.

The current policy marks a cycle `DEGRADED` when at least one configured check succeeds and another fails; repeated cycles with no successful checks reach `DOWN` at the configured failure threshold. Recovery from `DOWN` requires the configured number of successful cycles. A device with no recent check beyond the stale threshold is presented as `UNKNOWN`, and disabled devices are `PAUSED`. Check-specific, latency, and packet-loss incidents recover only after consecutive qualifying results; intervening failures reset recovery confirmation.

## 4. API contracts

Routes are under `/api`. Responses use JSON; errors will use a consistent object with a stable error code, human-readable message, and optional field details. List routes will use bounded pagination. Measurement and incident history will support device and UTC time-range filters.

| Method and route | Contract |
|---|---|
| `GET /api/health` | Service/database health and version; no target checks |
| `GET /api/devices` | Paginated device summaries with derived state and latest available measurements |
| `POST /api/devices` | Validate and create a device; enforce count and interval limits |
| `GET /api/devices/{id}` | Device configuration and current summary |
| `PATCH /api/devices/{id}` | Partial validated update |
| `DELETE /api/devices/{id}` | Delete device and apply documented dependent-record policy |
| `POST /api/devices/{id}/check` | Run one bounded manual check cycle synchronously and return its persisted results; reject duplicate work |
| `POST /api/devices/{id}/pause` / `resume` | Change monitoring state |
| `GET /api/measurements` | Paginated measurements, optionally filtered by device/type/time |
| `GET /api/devices/{id}/measurements` | Device-scoped diagnostic history |
| `GET /api/incidents` | Paginated incidents with device, severity, state, and time filters |
| `GET /api/interfaces` | Local psutil interface state/counters/rates, explicitly identified as host-level statistics |
| `GET /api/topology` | Registered nodes and manually configured links |
| `GET /api/settings` | Effective non-secret settings and safe bounds |
| `WS /api/ws` | Live event stream for measurements, state transitions, and incidents |

FastAPI-generated OpenAPI is the interactive API reference. Mutations validate input; CORS and browser WebSocket origins are limited to configured local frontend origins.

## 5. Background worker design

- Start one lifecycle-managed scheduler during FastAPI startup and cancel/drain its tasks during shutdown.
- Reconcile enabled devices and their intervals from stored configuration. Maintain at most one active check job for each device/check pair.
- Gate execution through a global semaphore and per-check timeout. Ping uses a Windows `ping.exe` argument list without a shell; TCP uses bounded socket connections; DNS uses dnspython with explicit resolver and timeout configuration.
- Keep adapter results typed and explicit: success, refusal, timeout, DNS/resolution failure, process error, and unsupported/unavailable are distinct outcomes.
- Persist each completed result, update state/incident transitions transactionally, and publish events only after persistence succeeds.
- Use configurable consecutive-failure thresholds, recovery confirmations, latency/loss thresholds, and stale-data duration. Repeated incidents deduplicate by device and incident kind until recovery.
- Sample psutil counters on a bounded cadence; calculate rates from counter deltas, and reset/mark unavailable on counter discontinuities.
- Apply measurement retention in limited-size deletion batches outside check execution. Database errors are logged and surfaced as service health/operation errors, not converted into successful measurements.

## 6. Security model

- Bind Uvicorn to `127.0.0.1`; do not enable public-network binding by default.
- Monitor only normalized, explicitly configured target names/IPs and TCP ports. No discovery scans or arbitrary-range probing.
- Validate host, port, interval, check type, and DNS record type with explicit limits. Reject command metacharacter inputs and never interpolate user input into a shell command.
- Use `asyncio.create_subprocess_exec`/safe argument lists for Windows ping; prohibit shell execution and general-purpose command endpoints.
- Bound concurrent checks, probe timeouts, ping count, response/history pagination, device count, and retention work.
- Restrict CORS and WebSocket origins, avoid storing credentials, keep local environment files out of version control, and expose only non-secret settings.
- Document Windows Firewall behavior: outbound ICMP/TCP/DNS may be filtered; Windows ping permissions and endpoint firewall policy can affect observations. A failed probe is evidence of a failed probe, not proof of device shutdown or root cause.

## 7. Milestones and test plan

| Milestone | Scope | Validation gate |
|---|---|---|
| 0 — Plan/scaffold | Architecture, target tree, conventions, and staged delivery | **Complete.** Plan, architecture diagram, and repository scaffold added. |
| 1 — Service and adapters | FastAPI lifecycle, SQLite schema initialization, ping/TCP/DNS adapters, health endpoint | **Complete.** Safe subprocess ping, TCP, DNS, health/OpenAPI, and explicit localhost integration coverage. |
| 2 — Management and state | Device CRUD, worker scheduling, measurements, thresholds, incidents, retention | **Complete.** CRUD, bounded lifecycle worker, persisted measurements, repeated-failure and recovery-confirmed incidents, and batched retention. |
| 3 — Dashboard | React shell, device management, summary/table, history and incident views | **Complete.** React/TypeScript dashboard uses backend data with empty, unavailable, and error states. |
| 4 — Live data and diagnostics | WebSocket with reconnect and polling fallback, charts, psutil interfaces, manually linked topology | **Complete.** WebSocket origin checks, reconnect test, history charts, host-level interface counters, and manual topology routes/view. |
| 5 — Hardening and packaging | Security/error review, docs, sample report, Windows setup, screenshots | **Implemented.** Localhost/CORS/origin restrictions, additive SQLite upgrade, bounded checks/retention, dependency audit, Windows instructions, and synthetic report template. Final smoke and test results are recorded in the handoff. |

Each milestone is delivered and verified before expanding scope. Network operations in ordinary tests are mocked; separate integration tests must target localhost or another explicitly approved endpoint. Test results will only be reported after commands actually run.
