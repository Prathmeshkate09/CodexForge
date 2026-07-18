import { useState } from "react";

import type { ExecutionRun } from "../../../shared/api/contracts";
import { ApprovalBadge } from "../../../shared/ui/status-badge";
import { formatDateTime, shortSha } from "../../../shared/utils/formatters";
import { usePlanApproval } from "../hooks";

export function PlanApprovalGate({ run }: { run: ExecutionRun }) {
  const [comment, setComment] = useState("");
  const decision = usePlanApproval(run.id);
  const { plan, plan_approval: approval } = run;

  if (!plan) {
    return (
      <section className="panel" aria-labelledby="plan-title">
        <p className="eyebrow">Approval gate one</p>
        <h2 id="plan-title" className="mt-1 text-xl font-semibold text-slate-950">
          Repository-evidenced plan
        </h2>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          CodexForge is still preparing a plan from the pinned repository snapshot. No patch work
          can start before a plan is available and approved.
        </p>
      </section>
    );
  }

  const canDecide = approval.status === "pending";
  const isBusy = decision.isPending;

  return (
    <section className="panel" aria-labelledby="plan-title">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="eyebrow">Approval gate one</p>
          <h2 id="plan-title" className="mt-1 text-xl font-semibold text-slate-950">
            Repository-evidenced plan
          </h2>
        </div>
        <ApprovalBadge status={approval.status} />
      </div>

      <p className="mt-4 text-sm leading-6 text-slate-700">{plan.summary}</p>
      <p className="mt-3 text-xs text-slate-500">
        Pinned snapshot: {shortSha(run.repository_commit_sha)}
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div>
          <h3 className="section-title">Proposed implementation</h3>
          <ol className="mt-3 space-y-3">
            {plan.steps.map((step, index) => (
              <li key={step.id} className="rounded-xl border border-slate-200 p-4">
                <p className="text-sm font-semibold text-slate-900">
                  {index + 1}. {step.title}
                </p>
                <p className="mt-1 text-sm leading-6 text-slate-600">{step.rationale}</p>
                {step.affected_paths.length > 0 ? (
                  <p className="mt-2 font-mono text-xs text-indigo-700">
                    {step.affected_paths.join(" · ")}
                  </p>
                ) : null}
              </li>
            ))}
          </ol>
        </div>
        <div>
          <h3 className="section-title">Repository evidence</h3>
          <ul className="mt-3 space-y-3">
            {plan.evidence.map((evidence) => (
              <li
                key={`${evidence.path}-${evidence.start_line ?? ""}`}
                className="rounded-xl border border-slate-200 p-4"
              >
                <p className="font-mono text-xs font-semibold text-slate-900">
                  {evidence.path}
                  {evidence.start_line ? `:${evidence.start_line}` : ""}
                </p>
                <p className="mt-1 text-sm leading-6 text-slate-600">{evidence.rationale}</p>
                <p className="mt-2 text-xs text-slate-500">
                  Commit {shortSha(evidence.commit_sha)}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {plan.risk_notes.length > 0 || plan.rollback_notes.length > 0 ? (
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl bg-amber-50 p-4">
            <h3 className="section-title text-amber-950">Risks</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-amber-900">
              {plan.risk_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl bg-slate-100 p-4">
            <h3 className="section-title">Rollback plan</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
              {plan.rollback_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      {canDecide ? (
        <div className="mt-7 rounded-xl border border-indigo-200 bg-indigo-50 p-5">
          <h3 className="text-sm font-semibold text-indigo-950">
            Your approval is required before any patch is generated.
          </h3>
          <label className="field-label mt-4" htmlFor="plan-approval-comment">
            Decision note (optional)
          </label>
          <textarea
            id="plan-approval-comment"
            className="field-control mt-1 bg-white"
            rows={3}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="Add constraints or explain why the plan should change."
          />
          {decision.isError ? (
            <p className="field-error" role="alert">
              {decision.error instanceof Error
                ? decision.error.message
                : "The plan decision could not be saved."}
            </p>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              className="button-primary"
              disabled={isBusy}
              onClick={() =>
                decision.mutate({ decision: "approve", comment: comment.trim() || undefined })
              }
            >
              {isBusy ? "Saving decision…" : "Approve plan"}
            </button>
            <button
              type="button"
              className="button-secondary"
              disabled={isBusy}
              onClick={() =>
                decision.mutate({ decision: "reject", comment: comment.trim() || undefined })
              }
            >
              Request a different plan
            </button>
          </div>
        </div>
      ) : (
        <p className="mt-6 text-sm text-slate-600">
          {approval.status === "approved" ? "Plan approved" : "Plan decision recorded"}
          {approval.decided_at ? ` on ${formatDateTime(approval.decided_at)}.` : "."}
        </p>
      )}
    </section>
  );
}
