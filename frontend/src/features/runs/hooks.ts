import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { PlanApprovalRequest, PullRequestApprovalRequest } from "../../shared/api/contracts";
import { approvePullRequestCreation, decidePlanApproval, getRun } from "./api";

export const runQueryKey = (runId: string) => ["runs", runId] as const;

export function useRun(runId: string, enabled: boolean) {
  return useQuery({
    queryKey: runQueryKey(runId),
    queryFn: () => getRun(runId),
    enabled: Boolean(runId) && enabled,
    refetchInterval: (query) => {
      const run = query.state.data;
      return run && ["complete", "failed", "cancelled"].includes(run.status) ? false : 10_000;
    },
  });
}

export function usePlanApproval(runId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: PlanApprovalRequest) => decidePlanApproval(runId, request),
    onSuccess: (run) => {
      queryClient.setQueryData(runQueryKey(runId), run);
    },
  });
}

export function usePullRequestApproval(runId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: PullRequestApprovalRequest) => approvePullRequestCreation(runId, request),
    onSuccess: (run) => {
      queryClient.setQueryData(runQueryKey(runId), run);
    },
  });
}
