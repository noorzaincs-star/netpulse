export type DeviceState = "UP" | "DEGRADED" | "DOWN" | "UNKNOWN" | "PAUSED";
export type CheckType = "icmp" | "tcp" | "dns";

export interface Measurement {
  id: string;
  device_id: string;
  check_type: CheckType;
  outcome: string;
  started_at: string;
  completed_at: string;
  latency_ms: number | null;
  packet_loss_percent: number | null;
  details: Record<string, unknown>;
  error: string | null;
}

export interface Device {
  id: string;
  name: string;
  hostname: string;
  device_type: string;
  description: string | null;
  tags: string[];
  enabled: boolean;
  interval_seconds: number;
  check_types: CheckType[];
  ping_count: number;
  check_timeout_seconds: number;
  tcp_port: number | null;
  dns_record_type: string;
  state: DeviceState;
  failure_count: number;
  recovery_count: number;
  created_at: string;
  updated_at: string;
  last_checked_at: string | null;
  latest_measurement: Pick<
    Measurement,
    "id" | "check_type" | "outcome" | "completed_at" | "latency_ms" | "packet_loss_percent"
  > | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Incident {
  id: string;
  device_id: string | null;
  kind: string;
  severity: string;
  status: string;
  started_at: string;
  recovered_at: string | null;
  duration_seconds: number | null;
  observed_facts: Record<string, unknown>;
  supporting_measurements: string[];
}

export interface NetworkInterface {
  name: string;
  is_up: boolean | null;
  speed_mbps: number | null;
  mtu: number | null;
  bytes_sent: number;
  bytes_received: number;
  bytes_sent_per_second: number | null;
  bytes_received_per_second: number | null;
  counter_reset: boolean;
  rate_available: boolean;
}

export interface InterfaceSnapshot {
  scope: "local_host_interfaces";
  sampled_at: number;
  note: string;
  interfaces: NetworkInterface[];
}

export interface TopologyNode {
  id: string;
  name: string;
  hostname: string;
  device_type: string;
  state: DeviceState;
  enabled: boolean;
}

export interface TopologyLink {
  id: string;
  source_device_id: string;
  target_device_id: string;
  label: string | null;
  created_at: string;
}
