import { useState, type FormEvent } from "react";
import { X } from "lucide-react";
import type { CheckType, Device } from "../types";

export interface DeviceForm {
  name: string;
  hostname: string;
  device_type: string;
  description: string;
  tags: string;
  enabled: boolean;
  interval_seconds: number;
  check_types: CheckType[];
  ping_count: number;
  check_timeout_seconds: number;
  tcp_port: string;
  dns_record_type: string;
}

const emptyForm: DeviceForm = {
  name: "",
  hostname: "",
  device_type: "server",
  description: "",
  tags: "",
  enabled: true,
  interval_seconds: 60,
  check_types: ["icmp"],
  ping_count: 3,
  check_timeout_seconds: 3,
  tcp_port: "",
  dns_record_type: "A",
};

function toForm(device?: Device): DeviceForm {
  if (!device) return emptyForm;
  return {
    name: device.name,
    hostname: device.hostname,
    device_type: device.device_type,
    description: device.description ?? "",
    tags: device.tags.join(", "),
    enabled: device.enabled,
    interval_seconds: device.interval_seconds,
    check_types: device.check_types,
    ping_count: device.ping_count,
    check_timeout_seconds: device.check_timeout_seconds,
    tcp_port: device.tcp_port?.toString() ?? "",
    dns_record_type: device.dns_record_type,
  };
}

interface DeviceDialogProps {
  device?: Device;
  onClose: () => void;
  onSave: (form: Record<string, unknown>, editing: boolean) => Promise<void>;
}

export default function DeviceDialog({ device, onClose, onSave }: DeviceDialogProps) {
  const [form, setForm] = useState<DeviceForm>(() => toForm(device));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editing = Boolean(device);

  const set = <K extends keyof DeviceForm>(key: K, value: DeviceForm[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  const toggleCheck = (check: CheckType) => {
    const checks = form.check_types.includes(check)
      ? form.check_types.filter((item) => item !== check)
      : [...form.check_types, check];
    set("check_types", checks);
  };

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const payload: Record<string, unknown> = {
      name: form.name.trim(),
      hostname: form.hostname.trim(),
      device_type: form.device_type,
      description: form.description.trim() || null,
      tags: form.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      enabled: form.enabled,
      interval_seconds: Number(form.interval_seconds),
      check_types: form.check_types,
      ping_count: Number(form.ping_count),
      check_timeout_seconds: Number(form.check_timeout_seconds),
      dns_record_type: form.dns_record_type,
    };
    if (form.check_types.includes("tcp")) payload.tcp_port = Number(form.tcp_port);
    else if (editing) payload.tcp_port = null;
    try {
      await onSave(payload, editing);
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save this device.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="device-dialog-title">
        <div className="modal-heading">
          <div>
            <span className="eyebrow">{editing ? "DEVICE CONFIGURATION" : "NEW MONITORED TARGET"}</span>
            <h2 id="device-dialog-title">{editing ? "Edit device" : "Add a device"}</h2>
          </div>
          <button className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={18} /></button>
        </div>
        <p className="muted small">NetPulse checks only the host and ports you explicitly configure.</p>
        <form onSubmit={submit} className="form-grid">
          <label className="field span-two">
            <span>Device name</span>
            <input autoFocus required maxLength={120} value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. Office gateway" />
          </label>
          <label className="field span-two">
            <span>Hostname or IP address</span>
            <input required maxLength={253} value={form.hostname} onChange={(e) => set("hostname", e.target.value)} placeholder="192.168.1.1 or gateway.local" />
          </label>
          <label className="field">
            <span>Device type</span>
            <select value={form.device_type} onChange={(e) => set("device_type", e.target.value)}>
              {["server", "router", "switch", "workstation", "printer", "nas", "other"].map((item) => <option key={item} value={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Interval</span>
            <select value={form.interval_seconds} onChange={(e) => set("interval_seconds", Number(e.target.value))}>
              {[10, 30, 60, 120, 300, 600, 1800, 3600].map((seconds) => <option key={seconds} value={seconds}>{seconds < 60 ? `${seconds} sec` : `${seconds / 60} min`}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Check timeout</span>
            <input type="number" min={0.1} max={30} step={0.1} required value={form.check_timeout_seconds} onChange={(e) => set("check_timeout_seconds", Number(e.target.value))} />
          </label>
          <fieldset className="check-options span-two">
            <legend>Checks</legend>
            {([
              ["icmp", "ICMP echo", "Windows ping"],
              ["tcp", "TCP connect", "Configured port"],
              ["dns", "DNS lookup", "Configured record type"],
            ] as const).map(([value, title, caption]) => (
              <label className="check-option" key={value}>
                <input type="checkbox" checked={form.check_types.includes(value)} onChange={() => toggleCheck(value)} />
                <span><strong>{title}</strong><small>{caption}</small></span>
              </label>
            ))}
            {form.check_types.length === 0 && <span className="field-error">Select at least one check.</span>}
          </fieldset>
          {form.check_types.includes("tcp") && (
            <label className="field span-two">
              <span>TCP port</span>
              <input type="number" min={1} max={65535} required value={form.tcp_port} onChange={(e) => set("tcp_port", e.target.value)} placeholder="443" />
            </label>
          )}
          {form.check_types.includes("icmp") && (
            <label className="field span-two">
              <span>Ping attempts</span>
              <input type="number" min={1} max={10} required value={form.ping_count} onChange={(e) => set("ping_count", Number(e.target.value))} />
            </label>
          )}
          {form.check_types.includes("dns") && (
            <label className="field span-two">
              <span>DNS record type</span>
              <select value={form.dns_record_type} onChange={(e) => set("dns_record_type", e.target.value)}>
                {["A", "AAAA", "CNAME", "MX", "NS", "PTR", "SOA", "SRV", "TXT"].map((type) => <option key={type}>{type}</option>)}
              </select>
            </label>
          )}
          <label className="field span-two">
            <span>Description <small>(optional)</small></span>
            <textarea maxLength={1000} rows={2} value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="Purpose, location, or owner" />
          </label>
          <label className="field span-two">
            <span>Tags <small>(comma separated)</small></span>
            <input value={form.tags} onChange={(e) => set("tags", e.target.value)} placeholder="production, branch-office" />
          </label>
          {editing && (
            <label className="toggle-row span-two">
              <input type="checkbox" checked={form.enabled} onChange={(e) => set("enabled", e.target.checked)} />
              <span>Monitoring enabled</span>
            </label>
          )}
          {error && <div className="form-error span-two" role="alert">{error}</div>}
          <div className="modal-actions span-two">
            <button type="button" className="button secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="button primary" disabled={saving || form.check_types.length === 0}>
              {saving ? "Saving…" : editing ? "Save changes" : "Add device"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
