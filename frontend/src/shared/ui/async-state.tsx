import type { ReactNode } from "react";

import { ApiError } from "../api/client";

interface StatePanelProps {
  title: string;
  children: ReactNode;
  action?: ReactNode;
  tone?: "default" | "danger";
}

function StatePanel({ title, children, action, tone = "default" }: StatePanelProps) {
  const color = tone === "danger" ? "border-red-200 bg-red-50" : "border-slate-200 bg-white";

  return (
    <section
      className={`rounded-2xl border p-7 shadow-panel ${color}`}
      aria-labelledby="state-title"
    >
      <h2 id="state-title" className="text-lg font-semibold text-slate-950">
        {title}
      </h2>
      <div className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{children}</div>
      {action ? <div className="mt-5">{action}</div> : null}
    </section>
  );
}

export function LoadingState({ label = "Loading workspace…" }: { label?: string }) {
  return (
    <div
      className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-7 shadow-panel"
      role="status"
    >
      <span
        className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600"
        aria-hidden="true"
      />
      <span className="text-sm font-medium text-slate-700">{label}</span>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const requestId = error instanceof ApiError ? error.requestId : undefined;
  const message = error instanceof Error ? error.message : "An unexpected error occurred.";

  return (
    <StatePanel
      title="We could not load this workspace"
      tone="danger"
      action={
        onRetry ? (
          <button type="button" className="button-secondary" onClick={onRetry}>
            Try again
          </button>
        ) : undefined
      }
    >
      <p role="alert">{message}</p>
      {requestId ? (
        <p className="mt-2 text-xs text-slate-500">Support reference: {requestId}</p>
      ) : null}
    </StatePanel>
  );
}

export function UnauthorizedState() {
  return (
    <StatePanel title="Sign in is required" tone="danger">
      <p role="alert">
        Your session cannot access this CodexForge workspace. Sign in again, then retry.
      </p>
    </StatePanel>
  );
}

export function EmptyState({ title, children, action }: Omit<StatePanelProps, "tone">) {
  return (
    <StatePanel title={title} action={action}>
      {children}
    </StatePanel>
  );
}
