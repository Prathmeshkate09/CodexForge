/**
 * Hand-maintained boundary types for the FastAPI `/api/v1` contract.
 *
 * Backend responses may use the `ApiEnvelope<T>` wrapper below. Keeping the
 * contract here makes replacing these types with generated OpenAPI types a
 * localized change rather than a UI rewrite.
 */
export interface ApiEnvelope<T> {
  data: T;
  request_id?: string;
}

export type WorkItemKind = "bug" | "feature" | "failed_ci";

export type RunStatus =
  | "draft"
  | "snapshot_pinned"
  | "plan_awaiting_approval"
  | "patch_ready"
  | "checks_queued"
  | "checks_running"
  | "review_ready"
  | "pr_awaiting_approval"
  | "complete"
  | "failed"
  | "cancelled";

export type ApprovalStatus = "not_required" | "pending" | "approved" | "rejected";

export interface Project {
  id: string;
  repository_full_name: string;
  default_branch: string;
  connection_status: "active" | "revoked" | "pending";
  created_at: string;
}

export interface CreateProjectRequest {
  repository_full_name: string;
  default_branch?: string;
  idempotency_key: string;
}

export interface WorkItem {
  id: string;
  project_id: string;
  kind: WorkItemKind;
  title: string;
  description: string;
  failed_ci_url?: string | null;
  created_at: string;
}

export interface RepositoryEvidence {
  path: string;
  start_line?: number | null;
  end_line?: number | null;
  commit_sha: string;
  rationale: string;
}

export interface PlanStep {
  id: string;
  title: string;
  rationale: string;
  affected_paths: string[];
}

export interface EvidenceBackedPlan {
  summary: string;
  steps: PlanStep[];
  evidence: RepositoryEvidence[];
  risk_notes: string[];
  rollback_notes: string[];
}

export interface TimelineEvent {
  id: string;
  occurred_at: string;
  title: string;
  detail: string;
  state: "complete" | "current" | "pending" | "failed";
}

export interface CheckEvidence {
  command_label: string;
  outcome: "passed" | "failed" | "not_run";
  summary: string;
  completed_at?: string | null;
}

export interface PullRequestReference {
  number: number;
  url: string;
  branch_name: string;
}

export interface ApprovalGate {
  status: ApprovalStatus;
  decided_at?: string | null;
  comment?: string | null;
}

export interface ExecutionRun {
  id: string;
  project_id: string;
  work_item: WorkItem;
  status: RunStatus;
  repository_commit_sha?: string | null;
  plan?: EvidenceBackedPlan | null;
  plan_approval: ApprovalGate;
  pull_request_approval: ApprovalGate;
  timeline: TimelineEvent[];
  patch_summary?: string | null;
  changed_paths: string[];
  check_evidence: CheckEvidence[];
  pull_request?: PullRequestReference | null;
  created_at: string;
  updated_at: string;
}

export interface CreateWorkItemRequest {
  project_id: string;
  kind: WorkItemKind;
  title: string;
  description: string;
  failed_ci_url?: string;
  idempotency_key: string;
}

export interface CreateWorkItemResponse {
  work_item: WorkItem;
  run: ExecutionRun;
}

export interface PlanApprovalRequest {
  decision: "approve" | "reject";
  comment?: string;
}

export interface PullRequestApprovalRequest {
  /** Explicit acknowledgement that GitHub branch/PR creation may begin. */
  approve_branch_and_pull_request_creation: true;
  comment?: string;
}
