import { apiFetch } from "../../shared/api/client";
import type { CreateWorkItemRequest, CreateWorkItemResponse } from "../../shared/api/contracts";

export function createWorkItem(request: CreateWorkItemRequest): Promise<CreateWorkItemResponse> {
  return apiFetch<CreateWorkItemResponse>("/work-items", {
    method: "POST",
    headers: {
      "Idempotency-Key": request.idempotency_key,
    },
    body: JSON.stringify(request),
  });
}
