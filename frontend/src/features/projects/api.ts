import { apiFetch } from "../../shared/api/client";
import type { CreateProjectRequest, Project } from "../../shared/api/contracts";

export function listProjects(): Promise<Project[]> {
  return apiFetch<Project[]>("/projects");
}

export function createProject(request: CreateProjectRequest): Promise<Project> {
  return apiFetch<Project>("/projects", {
    method: "POST",
    headers: {
      "Idempotency-Key": request.idempotency_key,
    },
    body: JSON.stringify(request),
  });
}
