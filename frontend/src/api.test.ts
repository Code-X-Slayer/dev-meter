import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

describe("API client", () => {
  afterEach(() => vi.restoreAllMocks());

  it("sends management credentials as a bearer token", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ username: "admin" }), { status: 200 }),
    ));

    await api.me("memory-only-token");

    expect(fetch).toHaveBeenCalledWith("/v1/auth/me", expect.objectContaining({
      headers: expect.objectContaining({
        Authorization: "Bearer memory-only-token",
      }),
    }));
  });

  it("notifies the app when the management token is rejected", async () => {
    const dispatchEvent = vi.fn();
    vi.stubGlobal("window", { dispatchEvent });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid token" }), { status: 401 }),
    ));

    await expect(api.me("expired-token")).rejects.toThrow("session has expired");

    expect(dispatchEvent).toHaveBeenCalledOnce();
    expect(dispatchEvent).toHaveBeenCalledWith(expect.any(Event));
  });

  it("keeps a newly created key secret in the response only", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        id: "key-id",
        service_id: "service-id",
        name: "demo",
        key_prefix: "dm_abc",
        created_at: "2026-01-01T00:00:00Z",
        revoked_at: null,
        secret: "dm_secret",
      }), { status: 201 }),
    ));

    const result = await api.createKey("memory-token", "service-id", "demo");

    expect(result.secret).toBe("dm_secret");
    expect("localStorage" in globalThis).toBe(false);
    expect("sessionStorage" in globalThis).toBe(false);
  });
});
