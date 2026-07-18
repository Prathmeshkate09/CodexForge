import { apiClientConfiguration } from "./config";

const apiBaseUrl = apiClientConfiguration.configured ? apiClientConfiguration.baseUrl : "";

export type ApiTokenProvider = () => Promise<string | null>;

let apiTokenProvider: ApiTokenProvider | null = null;

/**
 * Registered by the authentication provider. The client asks for a fresh token
 * on each protected request so Firebase can rotate expired ID tokens.
 */
export function setApiTokenProvider(provider: ApiTokenProvider | null): void {
  apiTokenProvider = provider;
}

export class ApiError extends Error {
  readonly status: number;
  readonly requestId?: string;

  constructor(message: string, status: number, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.requestId = requestId;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getErrorMessage(payload: unknown): string | undefined {
  if (!isRecord(payload)) {
    return undefined;
  }

  if (typeof payload.detail === "string") {
    return payload.detail;
  }

  if (typeof payload.message === "string") {
    return payload.message;
  }

  if (isRecord(payload.error)) {
    if (typeof payload.error.message === "string") {
      return payload.error.message;
    }

    if (typeof payload.error.detail === "string") {
      return payload.error.detail;
    }
  }

  return undefined;
}

function unwrapEnvelope<T>(payload: unknown): T {
  if (isRecord(payload) && "data" in payload) {
    return payload.data as T;
  }

  return payload as T;
}

interface ApiFetchOptions extends RequestInit {
  requiresAuthentication?: boolean;
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  if (!apiClientConfiguration.configured) {
    throw new ApiError(apiClientConfiguration.message, 503);
  }

  const { requiresAuthentication = true, ...init } = options;
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (requiresAuthentication && !headers.has("Authorization")) {
    let token: string | null = null;

    try {
      token = (await apiTokenProvider?.()) ?? null;
    } catch {
      throw new ApiError(
        "Your sign-in token could not be refreshed. Sign in again and retry.",
        401,
      );
    }

    if (!token) {
      throw new ApiError("Sign in is required before accessing CodexForge.", 401);
    }

    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  const requestId = response.headers.get("x-request-id") ?? undefined;
  const contentType = response.headers.get("content-type") ?? "";
  let payload: unknown;

  if (contentType.includes("application/json")) {
    try {
      payload = await response.json();
    } catch {
      throw new ApiError("The server returned an invalid response.", 502, requestId);
    }
  }

  if (!response.ok) {
    const fallback =
      response.status === 401 ? "Your session has expired." : "The request could not be completed.";
    throw new ApiError(getErrorMessage(payload) ?? fallback, response.status, requestId);
  }

  return unwrapEnvelope<T>(payload);
}

export function createIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `cf-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
