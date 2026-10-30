# Database schema

## Initialization and upgrades

NetPulse uses SQLAlchemy's async engine with `aiosqlite`. At FastAPI startup, `Base.metadata.create_all` creates missing tables, then an idempotent additive migration checks the `devices` table and adds `ping_count` and `check_timeout_seconds` when absent. This supports databases created by earlier NetPulse builds that already have the device table. Back up `backend\netpulse.db` before upgrading.

Future schema changes that alter existing data or other tables require explicit migrations and upgrade tests; `create_all` alone does not modify existing table definitions. The default database is `sqlite+aiosqlite:///./netpulse.db`, resolved relative to the backend working directory. Override it with `NETPULSE_DATABASE_URL`.

## Tables

| Table | Purpose |
|---|---|
| `devices` | Explicitly configured targets, check selection, ping count, timeout, interval, state, and consecutive failure/recovery counters |
| `measurements` | Per-check outcomes, UTC start/completion times, latency, packet loss, typed details, and bounded error text |
| `incidents` | Incident kind/severity/status, deduplication key, start/recovery times, supporting measurement IDs, and observed facts |
| `alert_events` | Incident creation and recovery event history |
| `monitoring_config` | Reserved persisted monitoring configuration entity; effective runtime policy is currently loaded from environment settings |
| `topology_links` | User-configured source/target relationships; no automatic physical-link inference |

Measurements are indexed by device and completion time. Incidents are indexed by device/start time and deduplication key. Device and topology foreign keys declare deletion behavior, and SQLite foreign-key enforcement is enabled per connection.

## Time, retention, and concurrency

Application timestamps are UTC. SQLite does not preserve timezone metadata when materializing datetimes, so API boundaries normalize naïve loaded values as UTC. Measurement cleanup runs hourly in ordered batches of at most 1,000 rows older than `NETPULSE_RETENTION_DAYS`; incidents are retained. SQLAlchemy async sessions are used for application database work, and network operations do not run inside database transactions.
