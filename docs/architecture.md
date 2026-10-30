# NetPulse architecture

NetPulse is planned as a localhost-only web client backed by a lifecycle-managed Python service. Network observations originate only from configured checks; the browser renders persisted results and marks unavailable or stale values explicitly.

```mermaid
flowchart LR
    Browser["React + TypeScript UI"]
    API["FastAPI REST + WebSocket"]
    Scheduler["Lifecycle-managed scheduler"]
    Policy["Validation + state/incident policy"]
    DB[("SQLite via SQLAlchemy")]
    Ping["Windows ping adapter"]
    TCP["TCP adapter"]
    DNS["DNS adapter"]
    IF["psutil interface sampler"]

    Browser -->|"REST: configuration/history"| API
    API -->|"WebSocket events; polling fallback"| Browser
    API --> Policy
    Policy <--> DB
    API -->|"manual checks"| Policy
    Scheduler -->|"scheduled checks"| Policy
    Policy --> Ping
    Policy --> TCP
    Policy --> DNS
    API --> IF
    Ping -->|"typed measurements"| Policy
    TCP -->|"typed measurements"| Policy
    DNS -->|"typed measurements"| Policy
    IF -->|"host-level counters/rates"| Policy
```

## Boundaries and guarantees

- A configured device is not evidence that it is currently reachable. Only completed checks produce measurements.
- ICMP, TCP, and DNS outcomes are independent. Ping failure alone does not establish that a device is down.
- Interface counters describe the local host's network interfaces, not per-device bandwidth.
- Topology edges are manually configured. Ping and TCP outcomes do not discover physical network links.
- Staleness, unavailable measurements, and check errors remain distinct from live successful results.
