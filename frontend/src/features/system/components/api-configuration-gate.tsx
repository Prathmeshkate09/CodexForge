import { apiClientConfiguration } from "../../../shared/api/config";
import { EmptyState } from "../../../shared/ui/async-state";

export function ApiConfigurationGate() {
  const message = apiClientConfiguration.configured
    ? "The API configuration is available."
    : apiClientConfiguration.message;

  return (
    <EmptyState title="API transport is not configured">
      <p role="alert">{message}</p>
      <p className="mt-4">
        Firebase Hosting does not currently proxy <code>/api/v1</code>. Set{" "}
        <code>VITE_API_BASE_URL</code> to the HTTPS Cloud Run API origin, including{" "}
        <code>/api/v1</code>, for Firebase or Cloud deployments. Docker Compose alone may use the
        explicit <code>local-container-proxy</code> transport mode with{" "}
        <code>VITE_API_BASE_URL=/api/v1</code>. CodexForge will not send protected API requests
        until this configuration is valid.
      </p>
    </EmptyState>
  );
}
