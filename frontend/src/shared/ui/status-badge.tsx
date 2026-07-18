import type { ApprovalStatus, RunStatus } from "../api/contracts";

const runLabels: Record<RunStatus, string> = {
  draft: "Draft",
  snapshot_pinned: "Repository snapshot pinned",
  plan_awaiting_approval: "Plan approval required",
  patch_ready: "Patch ready",
  checks_queued: "Checks queued",
  checks_running: "Checks running",
  review_ready: "Review ready",
  pr_awaiting_approval: "PR approval required",
  complete: "Complete",
  failed: "Failed",
  cancelled: "Cancelled",
};

const approvalLabels: Record<ApprovalStatus, string> = {
  not_required: "Not required",
  pending: "Approval required",
  approved: "Approved",
  rejected: "Rejected",
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const colors: Record<RunStatus, string> = {
    draft: "bg-slate-100 text-slate-700",
    snapshot_pinned: "bg-blue-100 text-blue-800",
    plan_awaiting_approval: "bg-amber-100 text-amber-900",
    patch_ready: "bg-indigo-100 text-indigo-800",
    checks_queued: "bg-slate-100 text-slate-700",
    checks_running: "bg-blue-100 text-blue-800",
    review_ready: "bg-emerald-100 text-emerald-800",
    pr_awaiting_approval: "bg-amber-100 text-amber-900",
    complete: "bg-emerald-100 text-emerald-800",
    failed: "bg-red-100 text-red-800",
    cancelled: "bg-slate-200 text-slate-700",
  };

  return <span className={`status-badge ${colors[status]}`}>{runLabels[status]}</span>;
}

export function ApprovalBadge({ status }: { status: ApprovalStatus }) {
  const colors: Record<ApprovalStatus, string> = {
    not_required: "bg-slate-100 text-slate-700",
    pending: "bg-amber-100 text-amber-900",
    approved: "bg-emerald-100 text-emerald-800",
    rejected: "bg-red-100 text-red-800",
  };

  return <span className={`status-badge ${colors[status]}`}>{approvalLabels[status]}</span>;
}
