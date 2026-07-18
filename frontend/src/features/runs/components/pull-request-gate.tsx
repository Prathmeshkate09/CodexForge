import { useState } from "react";

import type { ExecutionRun } from "../../../shared/api/contracts";
import { ApprovalBadge } from "../../../shared/ui/status-badge";
import { usePullRequestApproval } from "../hooks";

function safeGitHubPullRequestUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.hostname === "github.com" ? url.toString() : undefined;
  } catch {
    return undefined;
  }
}

export function PullRequestGate({ run }: { run: ExecutionRun }) {
  const [isConfirming, setIsConfirming] = useState(false);
  const [comment, setComment] = useState("");
  const approval = usePullRequestApproval(run.id);
  const canRequestPr = run.plan_approval.status === "approved" && run.status === "review_ready";
  const pullRequestUrl = run.pull_request
    ? safeGitHubPullRequestUrl(run.pull_request.url)
    : undefined;

  if (run.pull_request) {
    return (
      <section className="panel" aria-labelledby="pr-title">
        <p className="eyebrow">Approval gate two</p>
        <h2 id="pr-title" className="mt-1 text-xl font-semibold text-slate-950">
          Branch and pull request
        </h2>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          The approved change is available for normal GitHub review.
        </p>
        {pullRequestUrl ? (
          <a className="button-primary mt-5" href={pullRequestUrl} target="_blank" rel="noreferrer">
            Open pull request #{run.pull_request.number}
          </a>
        ) : (
          <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
            The API returned an invalid pull request URL. No external link was opened.
          </p>
        )}
      </section>
    );
  }

  return (
    <section className="panel" aria-labelledby="pr-title">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="eyebrow">Approval gate two</p>
          <h2 id="pr-title" className="mt-1 text-xl font-semibold text-slate-950">
            Branch and pull request creation
          </h2>
        </div>
        <ApprovalBadge status={run.pull_request_approval.status} />
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        Viewing this page cannot create a branch or pull request. GitHub write access is released
        only after you explicitly confirm this separate approval.
      </p>

      {!canRequestPr && run.pull_request_approval.status !== "approved" ? (
        <p className="mt-4 rounded-xl bg-slate-100 px-4 py-3 text-sm text-slate-700">
          This action is locked until the plan is approved and controlled checks are ready for
          review.
        </p>
      ) : null}

      {run.pull_request_approval.status === "approved" ? (
        <p className="mt-4 rounded-xl bg-indigo-50 px-4 py-3 text-sm text-indigo-900">
          Your approval is recorded. CodexForge may now create the branch and pull request through
          the controlled backend workflow.
        </p>
      ) : null}

      {canRequestPr && run.pull_request_approval.status === "pending" && !isConfirming ? (
        <button type="button" className="button-primary mt-5" onClick={() => setIsConfirming(true)}>
          Approve branch and pull request creation
        </button>
      ) : null}

      {canRequestPr && run.pull_request_approval.status === "pending" && isConfirming ? (
        <div className="mt-5 rounded-xl border border-amber-300 bg-amber-50 p-5">
          <h3 className="text-sm font-semibold text-amber-950">
            Confirm GitHub write authorization
          </h3>
          <p className="mt-2 text-sm leading-6 text-amber-900">
            This is the final approval. Confirming authorizes the backend to create a branch and a
            pull request for this reviewed patch.
          </p>
          <label className="field-label mt-4" htmlFor="pr-approval-comment">
            Review note (optional)
          </label>
          <textarea
            id="pr-approval-comment"
            className="field-control mt-1 bg-white"
            rows={3}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="Optional context for reviewers."
          />
          {approval.isError ? (
            <p className="field-error" role="alert">
              {approval.error instanceof Error
                ? approval.error.message
                : "The GitHub approval could not be recorded."}
            </p>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              className="button-danger"
              disabled={approval.isPending}
              onClick={() =>
                approval.mutate({
                  approve_branch_and_pull_request_creation: true,
                  comment: comment.trim() || undefined,
                })
              }
            >
              {approval.isPending ? "Recording approval…" : "Confirm and authorize GitHub write"}
            </button>
            <button
              type="button"
              className="button-secondary"
              disabled={approval.isPending}
              onClick={() => setIsConfirming(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
