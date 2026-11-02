import { afterEach, expect, it, vi } from "vitest";

afterEach(() => {
  vi.resetModules();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  delete window.huggingface;
});

it("derives API, documentation, and WebSocket URLs from VITE_API_URL", async () => {
  vi.stubEnv("VITE_API_URL", "https://api.example.test/");
  const fetchMock = vi.fn(async () =>
    Response.json({ status: "ok", database: "ok" }),
  );
  vi.stubGlobal("fetch", fetchMock);

  const { api, apiDocsUrl, socketUrl } = await import("../src/lib/api");

  await expect(api.health()).resolves.toEqual({ status: "ok", database: "ok" });
  expect(fetchMock).toHaveBeenCalledWith(
    "https://api.example.test/api/health",
    expect.objectContaining({ headers: {} }),
  );
  expect(apiDocsUrl).toBe("https://api.example.test/docs");
  expect(socketUrl()).toBe("wss://api.example.test/api/ws");
});

it("uses the Hugging Face runtime API URL when no build-time URL is set", async () => {
  vi.stubEnv("VITE_API_URL", "");
  vi.stubEnv("PROD", true);
  window.huggingface = {
    variables: { NETPULSE_API_URL: "https://netpulse-backend.onrender.com/" },
  };
  const fetchMock = vi.fn(async () =>
    Response.json({ status: "ok", database: "ok" }),
  );
  vi.stubGlobal("fetch", fetchMock);

  const { api, socketUrl } = await import("../src/lib/api");

  await api.health();
  expect(fetchMock).toHaveBeenCalledWith(
    "https://netpulse-backend.onrender.com/api/health",
    expect.objectContaining({ headers: {} }),
  );
  expect(socketUrl()).toBe("wss://netpulse-backend.onrender.com/api/ws");
});
