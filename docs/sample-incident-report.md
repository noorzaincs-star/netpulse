# Sample incident report

> **Illustrative synthetic example only.** The target, timestamps, outcomes, and measurement IDs below are invented to show the report format. They are not measurements from this machine, do not appear in the live dashboard, and do not establish a real incident.

| Field | Example |
|---|---|
| Device | Example branch gateway (`192.0.2.10`, documentation-only address) |
| Incident | Device unavailable after consecutive configured ICMP failures |
| Severity / state | Critical / recovered |
| Start / recovery | `2025-01-15T10:12:00Z` / `2025-01-15T10:14:30Z` (synthetic) |
| Duration | 150 seconds (synthetic) |
| Observed facts | Three consecutive ICMP check cycles failed; each recorded 100% packet loss and no latency; two later successful cycles confirmed recovery. |
| Supporting measurements | Synthetic IDs `example-measurement-101` through `example-measurement-105` |
| Probable explanations | Unknown. Filtering, route interruption, target downtime, or transient packet loss would require independent evidence to distinguish. |
| Root cause | Not determined. A failed echo check alone does not establish that the device was down. |

Real incident records are generated from persisted monitoring results and threshold transitions. NetPulse reports observed measurements separately from hypotheses and does not fabricate explanations.
