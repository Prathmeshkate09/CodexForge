import { Link, useParams } from "react-router-dom";

import { AuthenticationGate } from "../features/auth/components/authentication-gate";
import { useAuth } from "../features/auth/auth-context";
import { PlanApprovalGate } from "../features/runs/components/plan-approval-gate";
import { PatchReviewCard } from "../features/runs/components/patch-review-card";
import { PullRequestGate } from "../features/runs/components/pull-request-gate";
import { RunTimeline } from "../features/runs/components/run-timeline";
import { useRun } from "../features/runs/hooks";
import { ApiError } from "../shared/api/client";
import { apiClientConfiguration } from "../shared/api/config";
import { ErrorState, LoadingState, UnauthorizedState } from "../shared/ui/async-state";
import { ApiConfigurationGate } from "../features/system/components/api-configuration-gate";
import { RunStatusBadge } from "../shared/ui/status-badge";
import { formatDateTime, shortSha } from "../shared/utils/formatters";

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const auth = useAuth();
  const runQuery = useRun(runId, auth.canAccessProtectedApi && apiClientConfiguration.configured);

  if (!apiClientConfiguration.configured) {
    return <ApiConfigurationGate />;
  }

  if (!auth.canAccessProtectedApi) {
    return <AuthenticationGate />;
  }

  if (!runId) {
    return <ErrorState error={new Error("This run identifier is invalid.")} />;
  }

  if (runQuery.isLoading) {
    return <LoadingState label="Loading work item…" />;
  }

  if (runQuery.isError) {
    if (runQuery.error instanceof ApiError && [401, 403].includes(runQuery.error.status)) {
      return <UnauthorizedState />;
    }

    return <ErrorState error={runQuery.error} onRetry={() => void runQuery.refetch()} />;
  }

  const run = runQuery.data;
  if (!run) {
    return <ErrorState error={new Error("The work item was not found.")} />;
  }

  return (
    <div className="space-y-7">
      <Link
        className="inline-flex items-center text-sm font-medium text-indigo-700 hover:text-indigo-800"
        to="/"
      >
        ← Back to workspace
      </Link>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-panel sm:p-7">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="eyebrow">{run.work_item.kind.replace("_", " ")}</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">
              {run.work_item.title}
            </h1>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">
              {run.work_item.description}
            </p>
          </div>
          <RunStatusBadge status={run.status} />
        </div>
        <dl className="mt-6 grid gap-3 border-t border-slate-100 pt-5 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Started</dt>
            <dd className="mt-1 text-slate-800">{formatDateTime(run.created_at)}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Repository snapshot
            </dt>
            <dd className="mt-1 font-mono text-slate-800">{shortSha(run.repository_commit_sha)}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Last update
            </dt>
            <dd className="mt-1 text-slate-800">{formatDateTime(run.updated_at)}</dd>
          </div>
        </dl>
      </section>

      <div className="grid gap-7 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-7">
          <PlanApprovalGate run={run} />
          <PatchReviewCard run={run} />
          <PullRequestGate run={run} />
        </div>
        <aside className="panel h-fit" aria-labelledby="timeline-title">
          <p className="eyebrow">Audit trail</p>
          <h2 id="timeline-title" className="mt-1 text-xl font-semibold text-slate-950">
            Workflow timeline
          </h2>
          <div className="mt-5">
            <RunTimeline events={run.timeline} />
          </div>
        </aside>
      </div>
    </div>
  );
}
