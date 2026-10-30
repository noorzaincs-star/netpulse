import type { Device, Incident, InterfaceSnapshot, Measurement } from "../src/types";
import { vi } from "vitest";

export const device: Device = {
  id: "device-1",
  name: "Edge gateway",
  hostname: "192.0.2.1",
  device_type: "router",
  description: null,
  tags: ["office"],
  enabled: true,
  interval_seconds: 30,
  check_types: ["icmp"],
  ping_count: 3,
  check_timeout_seconds: 3,
  tcp_port: null,
  dns_record_type: "A",
  state: "UP",
  failure_count: 0,
  recovery_count: 1,
  created_at: "2026-10-29T12:00:00Z",
  updated_at: "2026-10-29T12:01:00Z",
  last_checked_at: "2026-10-29T12:01:00Z",
  latest_measurement: {
    id: "measurement-1",
    check_type: "icmp",
    outcome: "success",
    completed_at: "2026-10-29T12:01:00Z",
    latency_ms: 3.2,
    packet_loss_percent: 0,
  },
};

export const measurement: Measurement = {
  id: "measurement-1",
  device_id: device.id,
  check_type: "icmp",
  outcome: "success",
  started_at: "2026-10-29T12:01:00Z",
  completed_at: "2026-10-29T12:01:00Z",
  latency_ms: 3.2,
  packet_loss_percent: 0,
  details: { attempts: 1, replies: 1 },
  error: null,
};

export const incident: Incident = {
  id: "incident-1",
  device_id: device.id,
  kind: "high_latency",
  severity: "warning",
  status: "active",
  started_at: "2026-10-29T12:01:00Z",
  recovered_at: null,
  duration_seconds: 12,
  observed_facts: { latency_ms: 275, threshold_ms: 250 },
  supporting_measurements: [measurement.id],
};

export const interfaces: InterfaceSnapshot = {
  scope: "local_host_interfaces",
  sampled_at: Date.now() / 1000,
  note: "Local host interface counters only.",
  interfaces: [],
};

export function apiPayload(options: {
  devices?: Device[];
  incidents?: Incident[];
  measurements?: Measurement[];
  fail?: boolean;
} = {}) {
  const { devices = [], incidents = [], measurements = [], fail = false } = options;
  const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 100 });
  return vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const url = new URL(String(input));
    if (fail) return new Response(JSON.stringify({ error: { code: "api_offline", message: "API is offline." } }), { status: 503 });
    if (url.pathname.endsWith("/devices")) return Response.json(page(devices));
    if (url.pathname.endsWith("/incidents")) return Response.json(page(incidents));
    if (url.pathname.endsWith("/measurements")) return Response.json(page(measurements));
    if (url.pathname.endsWith("/interfaces")) return Response.json(interfaces);
    if (url.pathname.endsWith("/topology")) return Response.json({ nodes: [], links: [], relationships_note: "Manual only" });
    if (url.pathname.endsWith("/settings")) return Response.json({});
    if (url.pathname.endsWith("/health")) return Response.json({ status: "ok", database: "ok" });
    return new Response(null, { status: 404 });
  });
}
