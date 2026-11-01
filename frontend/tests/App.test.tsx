import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/app/App";
import { apiPayload, device, incident, measurement } from "./fixtures";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  readyState: number = WebSocket.CONNECTING;

  constructor() {
    MockWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.readyState = WebSocket.OPEN;
      this.onopen?.(new Event("open"));
    });
  }

  close() {
    this.readyState = WebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close"));
  }

  send() {}
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  MockWebSocket.instances = [];
});

function renderApp(fetchMock: ReturnType<typeof apiPayload>) {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket);
  return render(<App />);
}

describe("NetPulse dashboard states", () => {
  it("shows a loading state while the local API is pending", async () => {
    let release!: () => void;
    const pending = new Promise<void>((resolve) => { release = resolve; });
    const healthyFetch = apiPayload();
    let firstRequestPending = true;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (firstRequestPending) await pending;
      return healthyFetch(input);
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("WebSocket", MockWebSocket);
    render(<App />);
    expect(screen.getByRole("status")).toHaveTextContent("Connecting to the local API");
    expect(screen.queryByRole("button", { name: "Add device" })).not.toBeInTheDocument();
    firstRequestPending = false;
    await act(async () => { release(); });
    expect(await screen.findAllByText("No devices configured")).not.toHaveLength(0);
  });

  it("shows an honest empty state without fabricated devices or measurements", async () => {
    renderApp(apiPayload());
    expect(await screen.findAllByText("No devices configured")).not.toHaveLength(0);
    expect(screen.getAllByText("Latency appears here after the first real check.")).not.toHaveLength(0);
    const summary = screen.getAllByText("Monitored devices")[0].closest(".summary-card");
    expect(summary).not.toBeNull();
    expect(within(summary as HTMLElement).getByText("0", { selector: ".summary-value" })).toBeInTheDocument();
  });

  it("reports API errors and keeps unavailable measurements unavailable", async () => {
    renderApp(apiPayload({ fail: true }));
    expect(await screen.findByRole("alert")).toHaveTextContent("API is offline.");
    expect(screen.getAllByText("No devices configured")).not.toHaveLength(0);
  });

  it("renders real backend device, measurements, and incident data", async () => {
    renderApp(apiPayload({ devices: [device], incidents: [incident], measurements: [measurement] }));
    expect(await screen.findAllByText("Edge gateway")).not.toHaveLength(0);
    expect(screen.getAllByText("Operational").length).toBeGreaterThan(0);
    expect(screen.getByText("3.2 ms")).toBeInTheDocument();
  });

  it("hides write controls in read-only public demo mode", async () => {
    renderApp(apiPayload({ devices: [device], publicDemoMode: true }));
    expect(await screen.findAllByText("Edge gateway")).not.toHaveLength(0);
    expect(screen.getByText("Read-only public demo. Scheduled checks use real measurements and are restricted to google.com and 8.8.8.8.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add device" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Check Edge gateway now" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit Edge gateway" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Devices/ }));
    expect(screen.queryByRole("button", { name: "Pause Edge gateway" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete Edge gateway" })).not.toBeInTheDocument();
  });

  it("exposes configurable ping count and timeout in the add-device form", async () => {
    const fetchMock = apiPayload();
    renderApp(fetchMock);
    await screen.findAllByText("No devices configured");
    fireEvent.click(screen.getAllByRole("button", { name: "Add device" })[0]);

    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Device name"), {
      target: { value: "Local test host" },
    });
    fireEvent.change(within(dialog).getByLabelText("Hostname or IP address"), {
      target: { value: "127.0.0.1" },
    });
    fireEvent.change(within(dialog).getByLabelText("Ping attempts"), {
      target: { value: "5" },
    });
    fireEvent.change(within(dialog).getByLabelText("Check timeout"), {
      target: { value: "2.5" },
    });

    expect(within(dialog).getByLabelText("Ping attempts")).toHaveValue(5);
    expect(within(dialog).getByLabelText("Check timeout")).toHaveValue(2.5);
  });
});
