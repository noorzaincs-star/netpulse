import type {
  Device,
  Incident,
  InterfaceSnapshot,
  Measurement,
  Page,
  TopologyLink,
  TopologyNode,
} from "../types";

const configuredApiOrigin =
  import.meta.env.VITE_API_URL ||
  window.huggingface?.variables?.NETPULSE_API_URL;
const missingHuggingFaceApiUrl =
  import.meta.env.PROD &&
  window.location.hostname.endsWith(".static.hf.space") &&
  !configuredApiOrigin;
export const apiConfigured = !missingHuggingFaceApiUrl;
const API_ORIGIN = (configuredApiOrigin || (import.meta.env.PROD
  ? window.location.origin
  : "http://127.0.0.1:8000")).replace(
  /\/+$/,
  "",
);
const API_BASE = `${API_ORIGIN}/api`;

export const apiDocsUrl = `${API_ORIGIN}/docs`;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!apiConfigured) {
    throw new ApiError(
      "Backend URL is missing. Deploy the Render API and set NETPULSE_API_URL in the Hugging Face Space variables.",
      0,
      "api_url_missing",
    );
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError("NetPulse API is unreachable.", 0, "network_error");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = body?.error;
    throw new ApiError(
      error?.message ?? `Request failed (${response.status}).`,
      response.status,
      error?.code,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; database: string }>("/health"),
  devices: (page = 1, pageSize = 100) =>
    request<Page<Device>>(`/devices?page=${page}&page_size=${pageSize}&sort=name`),
  devicesAll: async () => {
    const first = await api.devices(1, 100);
    const pages = await Promise.all(
      Array.from({ length: Math.ceil(first.total / first.page_size) - 1 }, (_, index) =>
        api.devices(index + 2, first.page_size),
      ),
    );
    return { ...first, items: [first, ...pages].flatMap((page) => page.items) };
  },
  createDevice: (payload: Record<string, unknown>) =>
    request<Device>("/devices", { method: "POST", body: JSON.stringify(payload) }),
  updateDevice: (id: string, payload: Record<string, unknown>) =>
    request<Device>(`/devices/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteDevice: (id: string) =>
    request<void>(`/devices/${encodeURIComponent(id)}`, { method: "DELETE" }),
  pauseDevice: (id: string) =>
    request<Device>(`/devices/${encodeURIComponent(id)}/pause`, { method: "POST" }),
  resumeDevice: (id: string) =>
    request<Device>(`/devices/${encodeURIComponent(id)}/resume`, { method: "POST" }),
  checkDevice: (id: string) =>
    request<{ device_id: string; measurements: Measurement[] }>(
      `/devices/${encodeURIComponent(id)}/check`,
      { method: "POST", body: JSON.stringify({}) },
    ),
  measurements: (limit = 100) =>
    request<Page<Measurement>>(`/measurements?page=1&page_size=${limit}`),
  deviceMeasurements: (id: string, limit = 100) =>
    request<Page<Measurement>>(
      `/devices/${encodeURIComponent(id)}/measurements?page=1&page_size=${limit}`,
    ),
  incidents: (limit = 100) =>
    request<Page<Incident>>(`/incidents?page=1&page_size=${limit}`),
  interfaces: () => request<InterfaceSnapshot>("/interfaces"),
  topology: () =>
    request<{ nodes: TopologyNode[]; links: TopologyLink[]; relationships_note: string }>(
      "/topology",
    ),
  createLink: (source_device_id: string, target_device_id: string, label: string) =>
    request<TopologyLink>("/topology/links", {
      method: "POST",
      body: JSON.stringify({ source_device_id, target_device_id, label }),
    }),
  deleteLink: (id: string) =>
    request<void>(`/topology/links/${encodeURIComponent(id)}`, { method: "DELETE" }),
  settings: () => request<Record<string, unknown>>("/settings"),
};

export function socketUrl(): string {
  const url = new URL(`${API_BASE}/ws`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}
