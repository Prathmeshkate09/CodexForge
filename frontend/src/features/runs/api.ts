import { apiFetch } from "../../shared/api/client";
import type {
  ExecutionRun,
  PlanApprovalRequest,
  PullRequestApprovalRequest,
} from "../../shared/api/contracts";

export function getRun(runId: string): Promise<ExecutionRun> {
  return apiFetch<ExecutionRun>(`/runs/${encodeURIComponent(runId)}`);
}

export function decidePlanApproval(
  runId: string,
  request: PlanApprovalRequest,
): Promise<ExecutionRun> {
  return apiFetch<ExecutionRun>(`/runs/${encodeURIComponent(runId)}/plan-approval`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function approvePullRequestCreation(
  runId: string,
  request: PullRequestApprovalRequest,
): Promise<ExecutionRun> {
  return apiFetch<ExecutionRun>(`/runs/${encodeURIComponent(runId)}/pull-request-approval`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}
