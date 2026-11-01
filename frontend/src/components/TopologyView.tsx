import { useMemo, useState, type PointerEvent, type WheelEvent } from "react";
import { Link2, Minus, Plus, Trash2 } from "lucide-react";
import type { DeviceState, TopologyLink, TopologyNode } from "../types";

const stateColors: Record<DeviceState, string> = {
  UP: "#48d6b5",
  DEGRADED: "#f4b740",
  DOWN: "#fb7185",
  UNKNOWN: "#8292a8",
  PAUSED: "#64748b",
};

interface TopologyViewProps {
  nodes: TopologyNode[];
  links: TopologyLink[];
  note: string;
  onCreateLink: (source: string, target: string, label: string) => Promise<void>;
  onDeleteLink: (id: string) => Promise<void>;
  readOnly?: boolean;
}

export default function TopologyView({
  nodes,
  links,
  note,
  onCreateLink,
  onDeleteLink,
  readOnly = false,
}: TopologyViewProps) {
  const [selected, setSelected] = useState<TopologyNode | null>(null);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [origin, setOrigin] = useState({ x: 0, y: 0 });
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [label, setLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const positions = useMemo(() => {
    const centerX = 440;
    const centerY = 250;
    const radius = Math.max(100, Math.min(205, nodes.length * 22));
    return new Map(nodes.map((node, index) => {
      const angle = (2 * Math.PI * index) / Math.max(nodes.length, 1) - Math.PI / 2;
      return [node.id, { x: centerX + Math.cos(angle) * radius, y: centerY + Math.sin(angle) * radius }];
    }));
  }, [nodes]);

  function onWheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    setScale((current) => Math.max(0.55, Math.min(1.8, current + (event.deltaY < 0 ? 0.08 : -0.08))));
  }

  function startPan(event: PointerEvent<SVGSVGElement>) {
    if ((event.target as Element).closest("[data-node]")) return;
    setDragging(true);
    setOrigin({ x: event.clientX - offset.x, y: event.clientY - offset.y });
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function movePan(event: PointerEvent<SVGSVGElement>) {
    if (dragging) setOffset({ x: event.clientX - origin.x, y: event.clientY - origin.y });
  }

  async function addLink() {
    if (!source || !target || source === target) {
      setError("Choose two different registered devices.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onCreateLink(source, target, label);
      setSource("");
      setTarget("");
      setLabel("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not add relationship.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="topology-layout">
      <section className="panel topology-canvas-panel">
        <div className="panel-heading topology-heading">
          <div>
            <span className="eyebrow">REGISTERED DEVICES</span>
            <h2>Network topology</h2>
          </div>
          <div className="zoom-controls">
            <button className="icon-button" aria-label="Zoom out" onClick={() => setScale((value) => Math.max(0.55, value - 0.1))}><Minus size={16} /></button>
            <span>{Math.round(scale * 100)}%</span>
            <button className="icon-button" aria-label="Zoom in" onClick={() => setScale((value) => Math.min(1.8, value + 0.1))}><Plus size={16} /></button>
            <button className="button secondary compact" onClick={() => { setScale(1); setOffset({ x: 0, y: 0 }); }}>Reset</button>
          </div>
        </div>
        <div className="topology-canvas-wrap">
          <svg
            className={`topology-canvas ${dragging ? "dragging" : ""}`}
            viewBox="0 0 880 500"
            role="img"
            aria-label="Interactive diagram of registered devices and manually configured links"
            onWheel={onWheel}
            onPointerDown={startPan}
            onPointerMove={movePan}
            onPointerUp={() => setDragging(false)}
            onPointerCancel={() => setDragging(false)}
          >
            <defs>
              <pattern id="topo-grid" width="32" height="32" patternUnits="userSpaceOnUse">
                <circle cx="1" cy="1" r="1" fill="#33465d" opacity=".45" />
              </pattern>
            </defs>
            <rect width="880" height="500" fill="url(#topo-grid)" />
            <g transform={`translate(${offset.x} ${offset.y}) translate(440 250) scale(${scale}) translate(-440 -250)`}>
              {links.map((link) => {
                const from = positions.get(link.source_device_id);
                const to = positions.get(link.target_device_id);
                if (!from || !to) return null;
                return (
                  <g key={link.id}>
                    <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="#48d6b5" strokeWidth="2" strokeDasharray="7 7" opacity=".68" />
                    {link.label && <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 8} textAnchor="middle" className="topology-link-label">{link.label}</text>}
                  </g>
                );
              })}
              {nodes.map((node) => {
                const point = positions.get(node.id)!;
                return (
                  <g
                    key={node.id}
                    data-node="true"
                    className="topology-node"
                    transform={`translate(${point.x} ${point.y})`}
                    onClick={() => setSelected(node)}
                    tabIndex={0}
                    role="button"
                    aria-label={`${node.name}, ${node.state}`}
                    onKeyDown={(event) => { if (event.key === "Enter") setSelected(node); }}
                  >
                    <circle r="30" fill="#13243a" stroke={stateColors[node.state]} strokeWidth="2" />
                    <circle r="7" fill={stateColors[node.state]} />
                    <text y="50" textAnchor="middle" className="topology-node-name">{node.name.slice(0, 18)}</text>
                    <text y="65" textAnchor="middle" className="topology-node-host">{node.hostname}</text>
                  </g>
                );
              })}
            </g>
          </svg>
          {nodes.length === 0 && (
            <div className="topology-empty">
              <div className="empty-icon"><Link2 size={22} /></div>
              <strong>No registered devices</strong>
              <span>Add configured devices to see them here.</span>
            </div>
          )}
        </div>
        <div className="topology-legend">
          {(["UP", "DEGRADED", "DOWN", "UNKNOWN", "PAUSED"] as DeviceState[]).map((state) => (
            <span key={state}><i style={{ backgroundColor: stateColors[state] }} />{state}</span>
          ))}
          <span className="topology-note">{note}</span>
        </div>
      </section>
      <aside className="topology-side">
        <section className="panel side-panel">
          <span className="eyebrow">DEVICE DETAILS</span>
          {selected ? (
            <div className="topology-detail">
              <span className={`status-dot ${selected.state.toLowerCase()}`} />
              <h3>{selected.name}</h3>
              <code>{selected.hostname}</code>
              <p>{selected.device_type} · {selected.state.toLowerCase()}</p>
            </div>
          ) : (
            <p className="muted small">Select a node to view its configured details.</p>
          )}
        </section>
        <section className="panel side-panel">
          <div className="panel-heading">
            <div><span className="eyebrow">MANUAL ONLY</span><h3>Relationships</h3></div>
            <Link2 size={17} className="muted" />
          </div>
          <p className="muted small">Connections are only shown when you add them. Ping does not reveal physical topology.</p>
          {readOnly ? (
            <p className="muted small">Relationships are read-only in the public demo.</p>
          ) : nodes.length >= 2 ? (
            <div className="link-form">
              <label className="field"><span>From</span>
                <select value={source} onChange={(event) => setSource(event.target.value)}><option value="">Select device</option>{nodes.map((node) => <option key={node.id} value={node.id}>{node.name}</option>)}</select>
              </label>
              <label className="field"><span>To</span>
                <select value={target} onChange={(event) => setTarget(event.target.value)}><option value="">Select device</option>{nodes.map((node) => <option key={node.id} value={node.id}>{node.name}</option>)}</select>
              </label>
              <label className="field"><span>Label <small>(optional)</small></span>
                <input value={label} maxLength={120} onChange={(event) => setLabel(event.target.value)} placeholder="uplink, same rack…" />
              </label>
              {error && <p className="field-error" role="alert">{error}</p>}
              <button className="button primary full-width" disabled={saving} onClick={() => void addLink()}>{saving ? "Adding…" : "Add relationship"}</button>
            </div>
          ) : <p className="muted small">Add at least two devices to configure a link.</p>}
          {links.length > 0 && (
            <div className="link-list">
              {links.map((link) => {
                const left = nodes.find((node) => node.id === link.source_device_id)?.name ?? "Unknown";
                const right = nodes.find((node) => node.id === link.target_device_id)?.name ?? "Unknown";
                return <div className="link-item" key={link.id}><span>{left} <i>↔</i> {right}<small>{link.label || "Manually configured"}</small></span>{!readOnly && <button className="icon-button danger" aria-label={`Remove ${left} to ${right} relationship`} onClick={() => void onDeleteLink(link.id)}><Trash2 size={15} /></button>}</div>;
              })}
            </div>
          )}
        </section>
      </aside>
    </div>
  );
}
