import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch, setApiTokenProvider } from "./client";

describe("apiFetch authentication", () => {
  afterEach(() => {
    setApiTokenProvider(null);
    vi.unstubAllGlobals();
  });

  it("attaches the current token from the registered provider", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: [] }), {
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    setApiTokenProvider(async () => "firebase-id-token");

    await apiFetch<unknown[]>("/projects");

    const request = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(request?.headers).get("Authorization")).toBe("Bearer firebase-id-token");
  });

  it("does not make a protected request without a token", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/projects")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
