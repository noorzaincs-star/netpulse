import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  Gauge,
  LayoutDashboard,
  LifeBuoy,
  Menu,
  Monitor,
  Network,
  Plus,
  Radio,
  RefreshCw,
  Search,
  Server,
  Settings2,
  ShieldCheck,
  Signal,
  SignalHigh,
  SignalLow,
  SignalZero,
  Sparkles,
  TriangleAlert,
  Wifi,
  X,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import DeviceDialog from "../components/DeviceDialog";
import TopologyView from "../components/TopologyView";
import { api, apiDocsUrl } from "../lib/api";
import { useNetPulse } from "../hooks/useNetPulse";
import type { Device, DeviceState, Incident, Measurement } from "../types";

type View = "overview" | "devices" | "incidents" | "topology";

const stateLabels: Record<DeviceState, string> = {
  UP: "Operational",
  DEGRADED: "Degraded",
  DOWN: "Unavailable",
  UNKNOWN: "Unknown",
  PAUSED: "Paused",
};

function formatTime(value: string | null | undefined): string {
  if (!value) return "No checks yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(date);
}

function formatAgo(value: string | null | undefined): string {
  if (!value) return "Never";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

function formatLatency(value: number | null | undefined): string {
  return value == null ? "—" : `${value.toFixed(value < 10 ? 1 : 0)} ms`;
}

function formatBytes(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  if (value < 1024) return `${value.toFixed(0)} B/s`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB/s`;
  return `${(value / 1024 / 1024).toFixed(2)} MB/s`;
}

function StatusBadge({ state }: { state: DeviceState }) {
  return <span className={`status-badge ${state.toLowerCase()}`}><i />{stateLabels[state]}</span>;
}

function ChartEmpty({ children }: { children: string }) {
  return <div className="chart-empty"><div className="empty-icon"><Activity size={20} /></div><span>{children}</span></div>;
}

function DeviceDetails({
  device,
  onClose,
}: {
  device: Device;
  onClose: () => void;
}) {
  const [history, setHistory] = useState<Measurement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.deviceMeasurements(device.id, 100)
      .then((response) => { if (active) setHistory(response.items); })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : "Could not load diagnostic history."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [device.id]);

  const chartData = [...history].reverse().filter((item) => item.latency_ms != null).map((item) => ({
    time: new Date(item.completed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    latency: item.latency_ms,
  }));
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="details-modal" role="dialog" aria-modal="true" aria-labelledby="device-detail-title">
        <div className="modal-heading">
          <div><span className="eyebrow">DEVICE DIAGNOSTICS</span><h2 id="device-detail-title">{device.name}</h2></div>
          <button className="icon-button" aria-label="Close details" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="detail-meta">
          <StatusBadge state={device.state} />
          <code>{device.hostname}</code>
          <span>{device.check_types.join(" · ").toUpperCase()}</span>
          <span>Last check {formatAgo(device.last_checked_at)}</span>
        </div>
        <div className="detail-stats">
          <div><span>Latest latency</span><strong>{formatLatency(device.latest_measurement?.latency_ms)}</strong></div>
          <div><span>Latest packet loss</span><strong>{device.latest_measurement?.packet_loss_percent == null ? "—" : `${device.latest_measurement.packet_loss_percent.toFixed(0)}%`}</strong></div>
          <div><span>Check interval</span><strong>{device.interval_seconds}s</strong></div>
          <div><span>Failure streak</span><strong>{device.failure_count}</strong></div>
        </div>
        <section className="panel detail-chart">
          <div className="panel-heading"><div><span className="eyebrow">MEASUREMENTS</span><h3>Latency history</h3></div><span className="chart-unit">milliseconds</span></div>
          {loading ? <ChartEmpty>Loading persisted measurements…</ChartEmpty> : error ? <div className="inline-error">{error}</div> : chartData.length ? (
            <ResponsiveContainer width="100%" height={185}>
              <AreaChart data={chartData}>
                <defs><linearGradient id="detailLatency" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#48d6b5" stopOpacity=".25" /><stop offset="100%" stopColor="#48d6b5" stopOpacity="0" /></linearGradient></defs>
                <CartesianGrid stroke="#243449" strokeDasharray="3 5" vertical={false} />
                <XAxis dataKey="time" tick={{ fill: "#8292a8", fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#8292a8", fontSize: 10 }} axisLine={false} tickLine={false} width={34} />
                <Tooltip contentStyle={{ background: "#111d2d", border: "1px solid #2a3b50", borderRadius: 10, color: "#e5edf6" }} />
                <Area type="monotone" dataKey="latency" stroke="#48d6b5" fill="url(#detailLatency)" strokeWidth={2} connectNulls={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <ChartEmpty>No latency measurements have been recorded for this device.</ChartEmpty>}
        </section>
        <section className="panel measurement-table-panel">
          <div className="panel-heading"><div><span className="eyebrow">CHECK HISTORY</span><h3>Recent diagnostics</h3></div><span className="muted small">{history.length} records</span></div>
          {loading ? <p className="muted small">Loading…</p> : history.length ? (
            <div className="measurement-list">
              {history.slice(0, 12).map((item) => (
                <div className="measurement-row" key={item.id}>
                  <span className={`measurement-indicator ${item.outcome === "success" ? "ok" : "bad"}`} />
                  <strong>{item.check_type.toUpperCase()}</strong>
                  <span className={item.outcome === "success" ? "text-success" : "text-danger"}>{item.outcome.replaceAll("_", " ")}</span>
                  <span>{formatLatency(item.latency_ms)}</span>
                  <time>{formatTime(item.completed_at)}</time>
                </div>
              ))}
            </div>
          ) : <p className="muted small">No persisted check results yet.</p>}
        </section>
      </section>
    </div>
  );
}

export default function App() {
  const data = useNetPulse();
  const readOnly = data.publicDemoMode !== false;
  const [view, setView] = useState<View>("overview");
  const [dialog, setDialog] = useState<"create" | "edit" | null>(null);
  const [editingDevice, setEditingDevice] = useState<Device | undefined>();
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<"name" | "state" | "last_checked_at">("name");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [interfaceHistory, setInterfaceHistory] = useState<{ time: string; sent: number; received: number }[]>([]);
  const [mobileNav, setMobileNav] = useState(false);

  useEffect(() => {
    const snapshot = data.interfaces;
    if (!snapshot) return;
    const current = snapshot.interfaces.filter(
      (item) => item.rate_available && item.bytes_sent_per_second != null && item.bytes_received_per_second != null,
    );
    if (!current.length) return;
    setInterfaceHistory((history) => [
      ...history.slice(-19),
      {
        time: new Date(snapshot.sampled_at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
        sent: current.reduce((sum, item) => sum + (item.bytes_sent_per_second ?? 0), 0),
        received: current.reduce((sum, item) => sum + (item.bytes_received_per_second ?? 0), 0),
      },
    ]);
  }, [data.interfaces]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const filteredDevices = useMemo(() => {
    const term = search.trim().toLowerCase();
    const filtered = data.devices.filter((device) =>
      !term ||
      device.name.toLowerCase().includes(term) ||
      device.hostname.toLowerCase().includes(term) ||
      device.tags.some((tag) => tag.toLowerCase().includes(term)),
    );
    return filtered.sort((a, b) => {
      const left = sortKey === "state" ? a.state : sortKey === "last_checked_at" ? a.last_checked_at ?? "" : a.name;
      const right = sortKey === "state" ? b.state : sortKey === "last_checked_at" ? b.last_checked_at ?? "" : b.name;
      return (left < right ? -1 : left > right ? 1 : 0) * (sortDirection === "asc" ? 1 : -1);
    });
  }, [data.devices, search, sortKey, sortDirection]);
  const pageSize = 10;
  const totalPages = Math.max(1, Math.ceil(filteredDevices.length / pageSize));
  const visibleDevices = filteredDevices.slice((page - 1) * pageSize, page * pageSize);
  const activeIncidents = data.incidents.filter((incident) => incident.status === "active");
  const onlineCount = data.devices.filter((device) => device.state === "UP").length;
  const degradedCount = data.devices.filter((device) => device.state === "DEGRADED").length;
  const chartMeasurements = [...data.measurements].reverse();
  const latencyData = chartMeasurements.filter((item) => item.latency_ms != null).map((item) => ({
    time: new Date(item.completed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    latency: item.latency_ms,
    check: item.check_type,
  }));
  const lossData = chartMeasurements.filter((item) => item.packet_loss_percent != null).map((item) => ({
    time: new Date(item.completed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    loss: item.packet_loss_percent,
    check: item.check_type,
  }));

  async function saveDevice(payload: Record<string, unknown>, editing: boolean) {
    if (editing && editingDevice) await api.updateDevice(editingDevice.id, payload);
    else await api.createDevice(payload);
    setToast(editing ? "Device configuration saved" : "Device added");
    await data.refresh();
  }

  async function runCheck(device: Device) {
    setBusyId(device.id);
    try {
      await api.checkDevice(device.id);
      setToast(`Check completed for ${device.name}`);
      await data.refresh();
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : "Manual check failed");
    } finally {
      setBusyId(null);
    }
  }

  async function toggleDevice(device: Device) {
    setBusyId(device.id);
    try {
      if (device.enabled) await api.pauseDevice(device.id);
      else await api.resumeDevice(device.id);
      setToast(device.enabled ? "Monitoring paused" : "Monitoring resumed");
      await data.refresh();
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : "Could not update device");
    } finally {
      setBusyId(null);
    }
  }

  async function removeDevice(device: Device) {
    if (!window.confirm(`Delete "${device.name}" and its measurement history?`)) return;
    try {
      await api.deleteDevice(device.id);
      setToast("Device deleted");
      await data.refresh();
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : "Could not delete device");
    }
  }

  async function createLink(source: string, target: string, label: string) {
    await api.createLink(source, target, label);
    await data.refresh();
  }

  async function deleteLink(id: string) {
    await api.deleteLink(id);
    await data.refresh();
  }

  function showEdit(device: Device) {
    setEditingDevice(device);
    setDialog("edit");
  }

  function changeSort(next: typeof sortKey) {
    if (next === sortKey) setSortDirection((direction) => direction === "asc" ? "desc" : "asc");
    else { setSortKey(next); setSortDirection("asc"); }
  }

  const activeViewTitle: Record<View, string> = {
    overview: "Network overview",
    devices: "Monitored devices",
    incidents: "Incident center",
    topology: "Network topology",
  };

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Activity size={20} strokeWidth={2.5} /></div>
          <div><strong>netpulse</strong><span>NETWORK OPERATIONS</span></div>
          <button className="mobile-close icon-button" aria-label="Close navigation" onClick={() => setMobileNav(false)}><X size={18} /></button>
        </div>
        <div className="workspace-switch"><span className="workspace-icon"><Network size={16} /></span><span><strong>{data.publicDemoMode === null ? "Connecting" : data.publicDemoMode ? "Public demo" : "Local workspace"}</strong><small>{data.publicDemoMode === null ? "Checking runtime mode" : data.publicDemoMode ? "Read-only · real checks" : "Private monitoring"}</small></span><ChevronDown size={15} /></div>
        <span className="nav-label">WORKSPACE</span>
        <nav className="main-nav" aria-label="Main navigation">
          <NavButton active={view === "overview"} icon={<LayoutDashboard size={17} />} label="Overview" onClick={() => { setView("overview"); setMobileNav(false); }} />
          <NavButton active={view === "devices"} icon={<Monitor size={17} />} label="Devices" count={data.totalDevices} onClick={() => { setView("devices"); setMobileNav(false); }} />
          <NavButton active={view === "incidents"} icon={<TriangleAlert size={17} />} label="Incidents" count={activeIncidents.length || undefined} onClick={() => { setView("incidents"); setMobileNav(false); }} />
          <NavButton active={view === "topology"} icon={<Network size={17} />} label="Topology" onClick={() => { setView("topology"); setMobileNav(false); }} />
        </nav>
        <div className="sidebar-bottom">
          <div className="scope-card"><ShieldCheck size={17} /><div><strong>{readOnly ? "Read-only access" : "Local &amp; private"}</strong><span>Only configured targets<br />are monitored.</span></div></div>
          <button className="nav-item support-item" onClick={() => window.open(apiDocsUrl, "_blank", "noopener,noreferrer")}><LifeBuoy size={17} /><span>API documentation</span><ChevronRight size={14} /></button>
          <div className="profile-row"><div className="avatar">NP</div><div><strong>NetPulse</strong><small>Local instance</small></div><Settings2 size={16} className="muted" /></div>
        </div>
      </aside>
      {mobileNav && <button className="nav-scrim" aria-label="Close menu" onClick={() => setMobileNav(false)} />}
      <main className="main-content">
        <header className="topbar">
          <div className="topbar-title">
            <button className="mobile-menu icon-button" aria-label="Open navigation" onClick={() => setMobileNav(true)}><Menu size={19} /></button>
            <span className="breadcrumb">Workspace <ChevronRight size={14} /> <strong>{activeViewTitle[view]}</strong></span>
          </div>
          <div className="topbar-actions">
            <span className={`connection-pill ${data.connection}`}><i />{data.connection === "live" ? "LIVE" : data.connection === "polling" ? "POLLING" : data.connection === "error" ? "OFFLINE" : "CONNECTING"}</span>
            <label className="refresh-select"><RefreshCw size={14} /><select aria-label="Refresh interval" value={data.refreshMs} onChange={(event) => data.setRefreshMs(Number(event.target.value))}><option value={5000}>5 sec</option><option value={10000}>10 sec</option><option value={30000}>30 sec</option><option value={60000}>1 min</option></select></label>
            <button className="icon-button refresh-button" aria-label="Refresh data" onClick={() => void data.refresh()}><RefreshCw size={16} /></button>
            <div className="topbar-avatar">N</div>
          </div>
        </header>

        <div className="page-content">
          {data.error && <div className="error-banner" role="alert"><AlertTriangle size={17} /><span>{data.error} <small>Showing the last successful data, if available.</small></span><button className="icon-button" onClick={() => void data.refresh()} aria-label="Retry"><RefreshCw size={15} /></button></div>}
          <div className="page-title-row">
            <div><div className="eyebrow page-eyebrow"><span className="pulse-dot" /> {data.publicDemoMode === null ? "READ-ONLY UNTIL CONNECTED" : data.publicDemoMode ? "PUBLIC LIVE DEMO" : "LOCAL MONITORING"}</div><h1>{activeViewTitle[view]}</h1><p className="page-subtitle">A clear view of your configured network checks and device health.</p></div>
            <div className="page-title-actions"><div className="last-updated"><Clock3 size={14} /><span>Updated {data.lastUpdated ? formatTime(data.lastUpdated.toISOString()) : "—"}</span></div>{!readOnly && <button className="button primary" onClick={() => { setEditingDevice(undefined); setDialog("create"); }}><Plus size={16} /> Add device</button>}</div>
          </div>
          {data.publicDemoMode && <div className="loading-banner" role="status">Read-only public demo. Scheduled checks use real measurements and are restricted to google.com and 8.8.8.8.</div>}
          {data.loading && !data.lastUpdated && <div className="loading-banner" role="status"><RefreshCw size={15} className="spin" /> Connecting to the local API and loading persisted measurements…</div>}

          {view === "overview" && (
            <>
              <div className="summary-grid">
                <SummaryCard icon={<Server size={17} />} label="Monitored devices" value={data.totalDevices} note={data.totalDevices ? `${data.devices.filter((item) => item.enabled).length} actively monitored` : "Configure your first target"} tone="mint" />
                <SummaryCard icon={<SignalHigh size={17} />} label="Operational" value={onlineCount} note="All configured checks responding" tone="blue" />
                <SummaryCard icon={<SignalLow size={17} />} label="Degraded" value={degradedCount} note="At least one check needs attention" tone="amber" />
                <SummaryCard icon={<AlertTriangle size={17} />} label="Active incidents" value={activeIncidents.length} note={activeIncidents.length ? "Requires attention" : "No active alerts"} tone={activeIncidents.length ? "rose" : "slate"} />
              </div>

              <div className="charts-grid">
                <section className="panel chart-panel">
                  <div className="panel-heading"><div><span className="eyebrow">RESPONSE TIME</span><h2>Latency history</h2></div><span className="chart-unit">ms <span className="legend-dot mint" />measured checks</span></div>
                  {latencyData.length ? (
                    <ResponsiveContainer width="100%" height={225}>
                      <AreaChart data={latencyData}>
                        <defs><linearGradient id="latencyFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#48d6b5" stopOpacity=".25" /><stop offset="100%" stopColor="#48d6b5" stopOpacity="0" /></linearGradient></defs>
                        <CartesianGrid stroke="#243449" strokeDasharray="3 5" vertical={false} />
                        <XAxis dataKey="time" tick={{ fill: "#8292a8", fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={25} />
                        <YAxis tick={{ fill: "#8292a8", fontSize: 10 }} axisLine={false} tickLine={false} width={36} />
                        <Tooltip contentStyle={{ background: "#111d2d", border: "1px solid #2a3b50", borderRadius: 10, color: "#e5edf6" }} formatter={(value) => [`${Number(value ?? 0).toFixed(2)} ms`, "Latency"]} />
                        <Area type="monotone" dataKey="latency" stroke="#48d6b5" fill="url(#latencyFill)" strokeWidth={2} connectNulls={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : <ChartEmpty>{data.loading ? "Waiting for measured checks…" : "Latency appears here after the first real check."}</ChartEmpty>}
                  <div className="chart-footer"><span><span className="legend-dot mint" />Measured backend results</span><span>{latencyData.length} samples</span></div>
                </section>
                <section className="panel chart-panel">
                  <div className="panel-heading"><div><span className="eyebrow">DELIVERY QUALITY</span><h2>Packet loss</h2></div><span className="chart-unit">percent <span className="legend-dot blue" />ICMP</span></div>
                  {lossData.length ? (
                    <ResponsiveContainer width="100%" height={225}>
                      <AreaChart data={lossData}>
                        <defs><linearGradient id="lossFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#74a7ff" stopOpacity=".22" /><stop offset="100%" stopColor="#74a7ff" stopOpacity="0" /></linearGradient></defs>
                        <CartesianGrid stroke="#243449" strokeDasharray="3 5" vertical={false} />
                        <XAxis dataKey="time" tick={{ fill: "#8292a8", fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={25} />
                        <YAxis domain={[0, 100]} tick={{ fill: "#8292a8", fontSize: 10 }} axisLine={false} tickLine={false} width={36} />
                        <Tooltip contentStyle={{ background: "#111d2d", border: "1px solid #2a3b50", borderRadius: 10, color: "#e5edf6" }} formatter={(value) => [`${Number(value ?? 0).toFixed(1)}%`, "Packet loss"]} />
                        <Area type="stepAfter" dataKey="loss" stroke="#74a7ff" fill="url(#lossFill)" strokeWidth={2} connectNulls={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : <ChartEmpty>{data.loading ? "Waiting for measured checks…" : "No packet-loss measurements recorded yet."}</ChartEmpty>}
                  <div className="chart-footer"><span><span className="legend-dot blue" />Loss from completed ping attempts</span><span>{lossData.length} samples</span></div>
                </section>
              </div>

              <div className="lower-grid">
                <section className="panel devices-panel">
                  <div className="panel-heading"><div><span className="eyebrow">YOUR TARGETS</span><h2>Device health</h2></div><button className="text-button" onClick={() => setView("devices")}>View all <ChevronRight size={14} /></button></div>
                  <DeviceTable
                    devices={data.devices.slice(0, 5)}
                    onSelect={setSelectedDevice}
                    onEdit={showEdit}
                    onCheck={runCheck}
                    onToggle={toggleDevice}
                    onDelete={removeDevice}
                    busyId={busyId}
                    compact
                    readOnly={readOnly}
                  />
                </section>
                <div className="side-stack">
                  <section className="panel traffic-panel">
                    <div className="panel-heading"><div><span className="eyebrow">LOCAL HOST</span><h2>Interface throughput</h2></div><Wifi size={16} className="muted" /></div>
                    <p className="muted small">Host interface counters · not per-device bandwidth</p>
                    {readOnly ? (
                      <div className="traffic-empty"><Gauge size={18} /><span>Local host interface statistics are not exposed in the public demo.</span></div>
                    ) : interfaceHistory.length ? (
                      <ResponsiveContainer width="100%" height={115}>
                        <AreaChart data={interfaceHistory}>
                          <defs><linearGradient id="trafficSent" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#74a7ff" stopOpacity=".2" /><stop offset="100%" stopColor="#74a7ff" stopOpacity="0" /></linearGradient><linearGradient id="trafficReceived" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#48d6b5" stopOpacity=".2" /><stop offset="100%" stopColor="#48d6b5" stopOpacity="0" /></linearGradient></defs>
                          <XAxis dataKey="time" hide /><YAxis hide /><Tooltip contentStyle={{ background: "#111d2d", border: "1px solid #2a3b50", borderRadius: 10, color: "#e5edf6" }} formatter={(value) => [formatBytes(Number(value ?? 0))]} />
                          <Area type="monotone" dataKey="received" stroke="#48d6b5" fill="url(#trafficReceived)" strokeWidth={1.7} />
                          <Area type="monotone" dataKey="sent" stroke="#74a7ff" fill="url(#trafficSent)" strokeWidth={1.7} />
                        </AreaChart>
                      </ResponsiveContainer>
                    ) : <div className="traffic-empty"><Gauge size={18} /><span>Rates become available after two interface samples.</span></div>}
                    {!readOnly && <div className="traffic-legend"><span><i className="legend-dot mint" />Received</span><strong>{formatBytes(interfaceHistory.at(-1)?.received)}</strong><span><i className="legend-dot blue" />Sent</span><strong>{formatBytes(interfaceHistory.at(-1)?.sent)}</strong></div>}
                  </section>
                  <section className="panel activity-panel">
                    <div className="panel-heading"><div><span className="eyebrow">RECENT EVENTS</span><h2>Activity</h2></div><Activity size={16} className="muted" /></div>
                    <ActivityFeed incidents={data.incidents.slice(0, 4)} measurements={data.measurements.slice(0, 5)} devices={data.devices} />
                  </section>
                </div>
              </div>
            </>
          )}

          {view === "devices" && (
            <section className="panel full-devices-panel">
              <div className="panel-heading devices-toolbar">
                <div><span className="eyebrow">DEVICE INVENTORY</span><h2>{data.totalDevices} registered target{data.totalDevices === 1 ? "" : "s"}</h2></div>
                <div className="table-actions"><label className="search-field"><Search size={15} /><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search name, host, or tag" /></label><button className="button secondary" onClick={() => void data.refresh()}><RefreshCw size={15} /> Refresh</button></div>
              </div>
              <DeviceTable
                devices={visibleDevices}
                onSelect={setSelectedDevice}
                onEdit={showEdit}
                onCheck={runCheck}
                onToggle={toggleDevice}
                onDelete={removeDevice}
                busyId={busyId}
                sortKey={sortKey}
                sortDirection={sortDirection}
                onSort={changeSort}
                readOnly={readOnly}
              />
              <div className="pagination"><span>Showing {filteredDevices.length ? (page - 1) * pageSize + 1 : 0}–{Math.min(page * pageSize, filteredDevices.length)} of {filteredDevices.length}</span><div><button className="icon-button" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}><ChevronLeft size={17} /></button><span>Page {page} of {totalPages}</span><button className="icon-button" aria-label="Next page" disabled={page >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}><ChevronRight size={17} /></button></div></div>
            </section>
          )}

          {view === "incidents" && <IncidentCenter incidents={data.incidents} devices={data.devices} />}

          {view === "topology" && (
            <TopologyView
              nodes={data.nodes}
              links={data.links}
              note="Relationships are configured manually."
              onCreateLink={createLink}
              onDeleteLink={deleteLink}
              readOnly={readOnly}
            />
          )}

          <footer className="page-footer"><span><ShieldCheck size={14} /> Local-first monitoring · No cloud telemetry</span><span>{readOnly ? "Host interface details hidden" : `${data.interfaces?.interfaces.length ?? 0} host interfaces detected`} <span className="footer-divider">·</span> <a href={apiDocsUrl} target="_blank" rel="noreferrer">API docs <ArrowUpRight size={12} /></a></span></footer>
        </div>
      </main>
      {dialog && (
        <DeviceDialog
          device={dialog === "edit" ? editingDevice : undefined}
          onClose={() => setDialog(null)}
          onSave={saveDevice}
        />
      )}
      {selectedDevice && <DeviceDetails device={selectedDevice} onClose={() => setSelectedDevice(null)} />}
      {toast && <div className="toast" role="status"><Check size={16} />{toast}<button className="icon-button" aria-label="Dismiss notification" onClick={() => setToast(null)}><X size={14} /></button></div>}
    </div>
  );
}

function NavButton({
  active,
  icon,
  label,
  count,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  count?: number;
  onClick: () => void;
}) {
  return <button className={`nav-item ${active ? "active" : ""}`} onClick={onClick}>{icon}<span>{label}</span>{count != null && <small>{count}</small>}</button>;
}

function SummaryCard({
  icon,
  label,
  value,
  note,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  note: string;
  tone: string;
}) {
  return <article className="panel summary-card"><div className={`summary-icon ${tone}`}>{icon}</div><div className="summary-label">{label}</div><div className="summary-value">{value}</div><div className="summary-note">{note}</div><div className={`summary-spark ${tone}`}><div /><div /><div /><div /><div /><div /><div /><div /><div /></div></article>;
}

function DeviceTable({
  devices,
  onSelect,
  onEdit,
  onCheck,
  onToggle,
  onDelete,
  busyId,
  compact = false,
  readOnly = false,
  sortKey,
  sortDirection,
  onSort,
}: {
  devices: Device[];
  onSelect: (device: Device) => void;
  onEdit: (device: Device) => void;
  onCheck: (device: Device) => void;
  onToggle: (device: Device) => void;
  onDelete: (device: Device) => void;
  busyId: string | null;
  compact?: boolean;
  readOnly?: boolean;
  sortKey?: "name" | "state" | "last_checked_at";
  sortDirection?: "asc" | "desc";
  onSort?: (key: "name" | "state" | "last_checked_at") => void;
}) {
  if (!devices.length) return <div className="device-empty"><div className="empty-icon"><Monitor size={20} /></div><strong>No devices configured</strong><span>When you add an authorized target, real check results will appear here.</span></div>;
  const sortButton = (key: "name" | "state" | "last_checked_at", label: string) => (
    <button className="sort-button" onClick={() => onSort?.(key)}>{label}{sortKey === key && <span>{sortDirection === "asc" ? "↑" : "↓"}</span>}</button>
  );
  return (
    <div className={`table-wrap ${compact ? "compact-table" : ""}`}>
      <table className="device-table">
        <thead><tr><th>DEVICE</th>{!compact && <th>TYPE</th>}<th>STATUS</th><th>LATENCY</th>{!compact && <th>LOSS</th>}<th>{sortButton("last_checked_at", "LAST CHECK")}</th>{!readOnly && <th aria-label="Actions" />}</tr></thead>
        <tbody>
          {devices.map((device) => {
            const busy = busyId === device.id;
            return (
              <tr key={device.id}>
                <td><button className="device-name-button" onClick={() => onSelect(device)}><span className="device-glyph"><Server size={16} /></span><span><strong>{device.name}</strong><small>{device.hostname}</small></span></button></td>
                {!compact && <td><span className="type-label">{device.device_type}</span></td>}
                <td><StatusBadge state={device.state} /></td>
                <td><span className={device.latest_measurement?.latency_ms != null ? "metric-value" : "metric-empty"}>{formatLatency(device.latest_measurement?.latency_ms)}</span></td>
                {!compact && <td><span className="metric-value">{device.latest_measurement?.packet_loss_percent == null ? "—" : `${device.latest_measurement.packet_loss_percent.toFixed(0)}%`}</span></td>}
                <td><span className="last-check-cell"><strong>{formatAgo(device.last_checked_at)}</strong><small>{formatTime(device.last_checked_at)}</small></span></td>
                {!readOnly && <td><div className="row-actions">
                  <button className="icon-button" aria-label={`Check ${device.name} now`} title="Check now" disabled={busy || !device.enabled} onClick={() => onCheck(device)}>{busy ? <RefreshCw size={15} className="spin" /> : <Zap size={15} />}</button>
                  <button className="icon-button" aria-label={`Edit ${device.name}`} title="Edit" onClick={() => onEdit(device)}><Settings2 size={15} /></button>
                  <button className="icon-button" aria-label={device.enabled ? `Pause ${device.name}` : `Resume ${device.name}`} title={device.enabled ? "Pause" : "Resume"} onClick={() => onToggle(device)}>{device.enabled ? <Signal size={15} /> : <SignalZero size={15} />}</button>
                  {!compact && <button className="icon-button danger" aria-label={`Delete ${device.name}`} title="Delete" onClick={() => onDelete(device)}><X size={15} /></button>}
                </div></td>}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ActivityFeed({
  incidents,
  measurements,
  devices,
}: {
  incidents: Incident[];
  measurements: Measurement[];
  devices: Device[];
}) {
  const activities = [
    ...incidents.map((incident) => ({
      id: incident.id,
      time: incident.started_at,
      title: incident.kind.replaceAll("_", " "),
      detail: devices.find((device) => device.id === incident.device_id)?.name ?? "Registered device",
      kind: incident.status === "active" ? "incident" : "recovered",
    })),
    ...measurements.map((measurement) => ({
      id: measurement.id,
      time: measurement.completed_at,
      title: `${measurement.check_type.toUpperCase()} ${measurement.outcome === "success" ? "check completed" : "check failed"}`,
      detail: devices.find((device) => device.id === measurement.device_id)?.name ?? "Registered device",
      kind: measurement.outcome === "success" ? "success" : "incident",
    })),
  ].sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime()).slice(0, 5);
  if (!activities.length) return <div className="activity-empty"><Sparkles size={16} /><span>Monitoring activity will appear after the first check.</span></div>;
  return <div className="activity-list">{activities.map((item) => <div className="activity-item" key={`${item.kind}-${item.id}`}><span className={`activity-marker ${item.kind}`}><i /></span><div><strong>{item.title}</strong><span>{item.detail}</span></div><time>{formatAgo(item.time)}</time></div>)}</div>;
}

function IncidentCenter({ incidents, devices }: { incidents: Incident[]; devices: Device[] }) {
  const [filter, setFilter] = useState<"all" | "active" | "recovered">("all");
  const filtered = incidents.filter((incident) => filter === "all" || incident.status === filter);
  return (
    <section className="panel incidents-panel">
      <div className="panel-heading incidents-toolbar"><div><span className="eyebrow">OBSERVED EVENTS</span><h2>Incident timeline</h2></div><div className="segmented-control">{(["all", "active", "recovered"] as const).map((value) => <button key={value} className={filter === value ? "selected" : ""} onClick={() => setFilter(value)}>{value[0].toUpperCase() + value.slice(1)}</button>)}</div></div>
      {!filtered.length ? <div className="device-empty"><div className="empty-icon"><ShieldCheck size={20} /></div><strong>No {filter === "all" ? "" : `${filter} `}incidents</strong><span>Incidents are created from repeated failed checks and observed thresholds.</span></div> : (
        <div className="incident-list">{filtered.map((incident) => {
          const device = devices.find((item) => item.id === incident.device_id);
          const duration = incident.duration_seconds == null ? "—" : incident.duration_seconds < 60 ? `${incident.duration_seconds.toFixed(0)} sec` : `${Math.floor(incident.duration_seconds / 60)} min`;
          const factValues = Object.entries(incident.observed_facts).filter(([key]) => key !== "recovery");
          return <article className="incident-row" key={incident.id}><div className={`incident-icon ${incident.status === "active" ? incident.severity : "recovered"}`}>{incident.status === "active" ? <TriangleAlert size={17} /> : <Check size={17} />}</div><div className="incident-main"><div className="incident-title-row"><h3>{incident.kind.replaceAll("_", " ")}</h3><span className={`incident-status ${incident.status}`}>{incident.status}</span><span className={`severity-label ${incident.severity}`}>{incident.severity}</span></div><p>{device?.name ?? "Device removed"} <code>{device?.hostname ?? ""}</code></p><div className="incident-facts">{factValues.slice(0, 3).map(([key, value]) => <span key={key}><small>{key.replaceAll("_", " ")}</small> {String(value)}</span>)}</div></div><div className="incident-time"><time>{formatTime(incident.started_at)}</time><span>Duration {duration}</span>{incident.recovered_at && <small>Recovered {formatTime(incident.recovered_at)}</small>}</div></article>;
        })}</div>
      )}
    </section>
  );
}
