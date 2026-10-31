import { afterEach, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
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
