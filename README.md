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

## Deploy on Render and Vercel

The API and frontend are deployed separately. Set the API origin (without `/api`) as the Vite build-time variable `VITE_API_URL`; the frontend derives its REST, WebSocket, and API-docs URLs from it.

### Render — backend

- **Root Directory:** `backend`
- **Build Command:** `python -m pip install -r requirements-lock.txt && python -m pip install --no-deps -e .`
- **Start Command:** `uvicorn netpulse.main:app --host 0.0.0.0 --port $PORT`
- **Environment:** set `CORS_ORIGINS` to the exact frontend origin, for example `https://netpulse.vercel.app`. Add comma-separated origins only for frontend deployments that should be allowed. Render's `RENDER_EXTERNAL_HOSTNAME` is accepted for the API host; set `NETPULSE_ALLOWED_HOSTS` to comma-separated hostnames if using a custom API domain.

### Vercel — frontend

- **Root Directory:** `frontend`
- **Install Command:** `npm ci`
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Environment Variable:** `VITE_API_URL=https://<your-render-service>.onrender.com`

Vercel builds the static site; it does not need a separate start command. Set `VITE_API_URL` in the Vercel project settings and redeploy after changing it. The URL must be the API origin, with no trailing slash or `/api`. Set `CORS_ORIGINS` on Render to the corresponding Vercel origin.

**Deployment limitations:** The API currently has no authentication. CORS and allowed-host checks are not authentication and do not prevent non-browser clients from calling the API. Do not expose real monitoring targets to a public API until authentication or equivalent access controls are in place. SQLite storage on a typical Render filesystem is ephemeral; use a persistent disk and a `NETPULSE_DATABASE_URL` on that disk if data must survive redeploys/restarts.

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

See [.env.example](.env.example) for local defaults and deployment variables, including CORS origins. The service binds to loopback by default; only the configured Render host is accepted when deployed, and remote WebSocket clients must send an explicitly allowed origin. Do not expose it without authentication and a deliberate security review.

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