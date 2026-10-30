# NetPulse

NetPulse is a local-first network monitoring and diagnostics application. It runs real ICMP, TCP, and DNS checks only for targets you explicitly configure, stores results in local SQLite, and presents measured data in a React dashboard. Empty, stale, and failed checks remain distinct; there is no fabricated live or demo data.

## Running application

![NetPulse dashboard captured from the running local application](docs/netpulse-dashboard.png)

This screenshot shows the live dashboard with no configured devices; interface throughput is measured from the local host.

## Features

- Device create/edit/delete, pause/resume, search, sorting, and manual checks.
- Scheduled ICMP, TCP, and DNS checks with per-device interval, timeout, and ping count.
- Consecutive-failure and recovery confirmation before device state and incident transitions.
- Persisted, paginated measurements and incidents; deduplicated active incidents.
- WebSocket updates with reconnect/backoff and REST polling fallback.
- Local-host interface counters and rates from psutil, clearly labeled as not per-device bandwidth.
- Manually configured topology links only; physical connectivity is never inferred from ping.
- FastAPI OpenAPI documentation and a responsive React dashboard.

## Run on Windows

Install Python 3.11 or newer and Node.js 20 or newer. Run these one-time setup commands in PowerShell from the project root:

```powershell
py -3.11 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-lock.txt
backend\.venv\Scripts\python.exe -m pip install --no-deps -e .\backend
Set-Location frontend
npm ci
```

To start NetPulse, open **two PowerShell windows** at the project root.

**Window 1 — API and monitoring worker:**

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m uvicorn netpulse.main:app --host 127.0.0.1 --port 8000
```

**Window 2 — web dashboard:**

```powershell
Set-Location frontend
npm run dev
```

Keep both windows open. Open `http://127.0.0.1:5173` for the dashboard or `http://127.0.0.1:8000/docs` for the API documentation. Press **Ctrl+C** in each window to stop its service. The SQLite database is created at `backend\netpulse.db` on first start.

Optionally, copy `.env.example` to `.env` in the project root to configure local limits.

## Test and build

```powershell
# Backend, from backend\
python -m pytest -q

# Frontend, from frontend\
npm test
npm run build
npm audit
```

## Configuration and safety

See [.env.example](.env.example) for database, concurrency, incident thresholds, stale-data, retention, and CORS settings. The service binds to loopback by default and rejects non-local HTTP hosts and untrusted WebSocket origins. Do not expose it on a LAN or public interface without adding authentication and a deliberate security review.

Add only devices and TCP ports you own or are authorized to monitor. NetPulse does not discover devices, scan address ranges, or execute arbitrary commands. Ping uses argument-list subprocess calls without a shell. Windows Firewall, endpoint policy, DNS configuration, and target-side filtering can block checks; a failed check is evidence of a failed probe, not proof that a device is offline or a root cause.

## Data and limitations

- Schema initialization uses SQLAlchemy `create_all` and applies an idempotent additive migration for device check-count and timeout columns. Back up `backend\netpulse.db` before upgrading. Other future schema changes must include explicit migrations.
- Measurement retention is applied in batches; incident records are retained.
- ICMP availability and latency depend on the target and Windows network policy. TCP and DNS measurements reflect only the configured endpoint or resolver.
- The topology graph displays registered devices and manually configured links only.
- Local interface counters measure the host's network interfaces, not an individual device's bandwidth.

## Documentation

- [Architecture](docs/architecture.md)
- [Implementation plan and verified milestones](docs/implementation-plan.md)
- [REST and WebSocket API](docs/api.md)
- [Database schema and retention](docs/database.md)
- [Illustrative incident report][def]

[def]: docs/sample-incident-report.md