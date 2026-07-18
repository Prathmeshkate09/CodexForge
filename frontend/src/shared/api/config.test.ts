import { describe, expect, it } from "vitest";

import { resolveApiClientConfiguration } from "./config";

describe("resolveApiClientConfiguration", () => {
  it("keeps the same-origin proxy default for development", () => {
    expect(resolveApiClientConfiguration({ DEV: true, PROD: false })).toEqual({
      configured: true,
      baseUrl: "/api/v1",
    });
  });

  it("rejects a missing production API endpoint", () => {
    expect(resolveApiClientConfiguration({ DEV: false, PROD: true })).toEqual({
      configured: false,
      message: "VITE_API_BASE_URL must be an HTTPS absolute API URL in production.",
    });
  });

  it("rejects non-HTTPS production endpoints", () => {
    expect(
      resolveApiClientConfiguration({
        DEV: false,
        PROD: true,
        VITE_API_BASE_URL: "http://api.example.com/api/v1",
      }),
    ).toEqual({
      configured: false,
      message: "VITE_API_BASE_URL must use an HTTPS absolute URL in production.",
    });
  });

  it("rejects the same-origin API path unless local container mode is explicit", () => {
    expect(
      resolveApiClientConfiguration({
        DEV: false,
        PROD: true,
        VITE_API_BASE_URL: "/api/v1",
      }),
    ).toEqual({
      configured: false,
      message: "VITE_API_BASE_URL must use an HTTPS absolute URL in production.",
    });
  });

  it("accepts the allowlisted same-origin API path only in explicit local container mode", () => {
    expect(
      resolveApiClientConfiguration({
        DEV: false,
        PROD: true,
        VITE_API_TRANSPORT_MODE: "local-container-proxy",
        VITE_API_BASE_URL: "/api/v1/",
      }),
    ).toEqual({
      configured: true,
      baseUrl: "/api/v1",
    });
  });

  it("rejects an HTTP target in local container proxy mode", () => {
    expect(
      resolveApiClientConfiguration({
        DEV: false,
        PROD: true,
        VITE_API_TRANSPORT_MODE: "local-container-proxy",
        VITE_API_BASE_URL: "http://localhost:8000/api/v1",
      }),
    ).toEqual({
      configured: false,
      message:
        "local-container-proxy only permits VITE_API_BASE_URL=/api/v1; it cannot target an external or HTTP API URL.",
    });
  });

  it("rejects an unknown production transport mode", () => {
    expect(
      resolveApiClientConfiguration({
        DEV: false,
        PROD: true,
        VITE_API_TRANSPORT_MODE: "development-proxy",
        VITE_API_BASE_URL: "https://api.example.com/api/v1",
      }),
    ).toEqual({
      configured: false,
      message: "VITE_API_TRANSPORT_MODE must be direct or local-container-proxy in production.",
    });
  });

  it("accepts a configured HTTPS production endpoint", () => {
    expect(
      resolveApiClientConfiguration({
        DEV: false,
        PROD: true,
        VITE_API_BASE_URL: "https://api.example.com/api/v1/",
      }),
    ).toEqual({
      configured: true,
      baseUrl: "https://api.example.com/api/v1",
    });
  });
});
