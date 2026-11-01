import { useCallback, useEffect, useRef, useState } from "react";
import { api, socketUrl } from "../lib/api";
import type {
  Device,
  Incident,
  InterfaceSnapshot,
  Measurement,
  TopologyLink,
  TopologyNode,
} from "../types";

export type ConnectionState = "connecting" | "live" | "polling" | "error";

interface NetPulseState {
  devices: Device[];
  totalDevices: number;
  incidents: Incident[];
  measurements: Measurement[];
  interfaces: InterfaceSnapshot | null;
  nodes: TopologyNode[];
  links: TopologyLink[];
  connection: ConnectionState;
  publicDemoMode: boolean | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  refresh: () => Promise<void>;
  setRefreshMs: (value: number) => void;
  refreshMs: number;
}

export function useNetPulse(): NetPulseState {
  const [devices, setDevices] = useState<Device[]>([]);
  const [totalDevices, setTotalDevices] = useState(0);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [interfaces, setInterfaces] = useState<InterfaceSnapshot | null>(null);
  const [nodes, setNodes] = useState<TopologyNode[]>([]);
  const [links, setLinks] = useState<TopologyLink[]>([]);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [publicDemoMode, setPublicDemoMode] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshMs, setRefreshMsState] = useState(10_000);
  const socketRef = useRef<WebSocket | null>(null);
  const retryTimer = useRef<number | undefined>(undefined);
  const retryDelay = useRef(500);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const results = await Promise.allSettled([
        api.devicesAll(),
        api.incidents(100),
        api.measurements(200),
        api.interfaces(),
        api.topology(),
        api.settings(),
      ]);
      const failed = results.find(
        (result): result is PromiseRejectedResult => result.status === "rejected",
      );
      if (failed) throw failed.reason;
      if (!mounted.current) return;
      const values = results.map(
        (result) => (result as PromiseFulfilledResult<unknown>).value,
      );
      const devicePage = values[0] as Awaited<ReturnType<typeof api.devicesAll>>;
      const incidentPage = values[1] as Awaited<ReturnType<typeof api.incidents>>;
      const measurementPage = values[2] as Awaited<ReturnType<typeof api.measurements>>;
      const interfaceData = values[3] as InterfaceSnapshot;
      const topologyData = values[4] as Awaited<ReturnType<typeof api.topology>>;
      const runtimeSettings = values[5] as { demo_mode?: boolean };
      setDevices(devicePage.items);
      setTotalDevices(devicePage.total);
      setIncidents(incidentPage.items);
      setMeasurements(measurementPage.items);
      setInterfaces(interfaceData);
      setNodes(topologyData.nodes);
      setLinks(topologyData.links);
      setPublicDemoMode(
        typeof runtimeSettings.demo_mode === "boolean"
          ? runtimeSettings.demo_mode
          : null,
      );
      setLastUpdated(new Date());
      setError(null);
      setLoading(false);
    } catch (reason) {
      if (!mounted.current) return;
      setError(reason instanceof Error ? reason.message : "Unable to load monitoring data.");
      setLoading(false);
      setConnection((current) => (current === "live" ? current : "error"));
    }
  }, []);

  const setRefreshMs = useCallback((value: number) => {
    setRefreshMsState(value);
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const polling = window.setInterval(() => void refresh(), refreshMs);
    let active = true;
    const connect = () => {
      if (!active) return;
      setConnection((current) => (current === "live" ? current : "connecting"));
      const socket = new WebSocket(socketUrl());
      socketRef.current = socket;
      socket.onopen = () => {
        retryDelay.current = 500;
        if (active) setConnection("live");
      };
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as { type?: string };
          if (message.type !== "keepalive") void refresh();
        } catch {
          void refresh();
        }
      };
      socket.onerror = () => socket.close();
      socket.onclose = () => {
        if (!active) return;
        setConnection("polling");
        retryTimer.current = window.setTimeout(connect, retryDelay.current);
        retryDelay.current = Math.min(retryDelay.current * 2, 15_000);
      };
    };
    connect();
    return () => {
      active = false;
      mounted.current = false;
      window.clearInterval(polling);
      if (retryTimer.current !== undefined) window.clearTimeout(retryTimer.current);
      socketRef.current?.close();
    };
  }, [refresh, refreshMs]);

  return {
    devices,
    totalDevices,
    incidents,
    measurements,
    interfaces,
    nodes,
    links,
    connection,
    publicDemoMode,
    loading,
    error,
    lastUpdated,
    refresh,
    setRefreshMs,
    refreshMs,
  };
}
