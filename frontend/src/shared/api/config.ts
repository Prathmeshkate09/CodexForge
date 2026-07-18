export interface ApiRuntimeEnvironment {
  DEV: boolean;
  PROD: boolean;
  VITE_API_BASE_URL?: string;
  VITE_API_TRANSPORT_MODE?: string;
}

export type ApiClientConfiguration =
  | {
      configured: true;
      baseUrl: string;
    }
  | {
      configured: false;
      message: string;
    };

function normalizeBaseUrl(value: string): string {
  return value.replace(/\/$/, "");
}

function isHttpsAbsoluteUrl(value: string): boolean {
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}

const localContainerProxyPath = "/api/v1";

function resolveLocalContainerProxyConfiguration(
  configuredValue: string | undefined,
): ApiClientConfiguration {
  if (!configuredValue) {
    return {
      configured: false,
      message:
        "VITE_API_BASE_URL must be /api/v1 when VITE_API_TRANSPORT_MODE is local-container-proxy.",
    };
  }

  const normalizedBaseUrl = normalizeBaseUrl(configuredValue);
  if (normalizedBaseUrl !== localContainerProxyPath) {
    return {
      configured: false,
      message:
        "local-container-proxy only permits VITE_API_BASE_URL=/api/v1; it cannot target an external or HTTP API URL.",
    };
  }

  return { configured: true, baseUrl: localContainerProxyPath };
}

/**
 * Firebase/Cloud production uses a direct HTTPS API URL. Docker Compose is the
 * sole exception: its Nginx container is explicitly built in
 * `local-container-proxy` mode and proxies the allowlisted same-origin path to
 * the local backend. This prevents a deployed Firebase SPA from silently
 * requesting its own HTML origin at `/api/v1`.
 */
export function resolveApiClientConfiguration(
  environment: ApiRuntimeEnvironment,
): ApiClientConfiguration {
  const configuredValue = environment.VITE_API_BASE_URL?.trim();
  const transportMode = environment.VITE_API_TRANSPORT_MODE?.trim();

  if (environment.PROD) {
    if (transportMode === "local-container-proxy") {
      return resolveLocalContainerProxyConfiguration(configuredValue);
    }

    if (transportMode && transportMode !== "direct") {
      return {
        configured: false,
        message: "VITE_API_TRANSPORT_MODE must be direct or local-container-proxy in production.",
      };
    }

    if (!configuredValue) {
      return {
        configured: false,
        message: "VITE_API_BASE_URL must be an HTTPS absolute API URL in production.",
      };
    }

    if (!isHttpsAbsoluteUrl(configuredValue)) {
      return {
        configured: false,
        message: "VITE_API_BASE_URL must use an HTTPS absolute URL in production.",
      };
    }

    return { configured: true, baseUrl: normalizeBaseUrl(configuredValue) };
  }

  return { configured: true, baseUrl: normalizeBaseUrl(configuredValue || "/api/v1") };
}

export const apiClientConfiguration = resolveApiClientConfiguration(import.meta.env);
