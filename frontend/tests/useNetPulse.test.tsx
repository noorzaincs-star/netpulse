import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useNetPulse } from "../src/hooks/useNetPulse";
import { apiPayload } from "./fixtures";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  readyState = 0;
  constructor() { MockWebSocket.instances.push(this); }
  open() { this.readyState = 1; this.onopen?.(new Event("open")); }
  close() { this.readyState = 3; this.onclose?.(new CloseEvent("close")); }
  send() {}
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  MockWebSocket.instances = [];
});

describe("useNetPulse live transport", () => {
  it("falls back to REST polling and reconnects the WebSocket with backoff", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", apiPayload());
    vi.stubGlobal("WebSocket", MockWebSocket);
    const { result } = renderHook(() => useNetPulse());
    await act(async () => { await Promise.resolve(); });
    expect(MockWebSocket.instances).toHaveLength(1);
    act(() => MockWebSocket.instances[0].open());
    expect(result.current.connection).toBe("live");

    act(() => MockWebSocket.instances[0].close());
    expect(result.current.connection).toBe("polling");
    await act(async () => { vi.advanceTimersByTime(600); });
    expect(MockWebSocket.instances).toHaveLength(2);
    expect(result.current.connection).toBe("connecting");
  });

  it("preserves the error state when REST requests are unavailable", async () => {
    vi.stubGlobal("fetch", apiPayload({ fail: true }));
    vi.stubGlobal("WebSocket", MockWebSocket);
    const { result } = renderHook(() => useNetPulse());
    await waitFor(() => expect(result.current.error).toBe("API is offline."));
  });
});
