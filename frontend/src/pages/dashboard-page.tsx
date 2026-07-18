import { useEffect, useState } from "react";

import { AuthenticationGate } from "../features/auth/components/authentication-gate";
import { useAuth } from "../features/auth/auth-context";
import { ApiConfigurationGate } from "../features/system/components/api-configuration-gate";
import { apiClientConfiguration } from "../shared/api/config";
import { ApiError } from "../shared/api/client";
import { ErrorState, LoadingState, UnauthorizedState } from "../shared/ui/async-state";
import { ProjectEmptyState } from "../features/projects/components/project-empty-state";
import { ProjectSelector } from "../features/projects/components/project-selector";
import { useProjects } from "../features/projects/hooks";
import { WorkItemForm } from "../features/work-items/components/work-item-form";

export function DashboardPage() {
  const auth = useAuth();
  const projectsQuery = useProjects(
    auth.canAccessProtectedApi && apiClientConfiguration.configured,
  );
  const [selectedProjectId, setSelectedProjectId] = useState("");

  useEffect(() => {
    if (!selectedProjectId && projectsQuery.data?.[0]) {
      setSelectedProjectId(projectsQuery.data[0].id);
    }
  }, [projectsQuery.data, selectedProjectId]);

  if (!apiClientConfiguration.configured) {
    return <ApiConfigurationGate />;
  }

  if (!auth.canAccessProtectedApi) {
    return <AuthenticationGate />;
  }

  if (projectsQuery.isLoading) {
    return <LoadingState label="Loading connected repositories…" />;
  }

  if (projectsQuery.isError) {
    if (
      projectsQuery.error instanceof ApiError &&
      [401, 403].includes(projectsQuery.error.status)
    ) {
      return <UnauthorizedState />;
    }

    return <ErrorState error={projectsQuery.error} onRetry={() => void projectsQuery.refetch()} />;
  }

  const projects = projectsQuery.data ?? [];
  const selectedProject =
    projects.find((project) => project.id === selectedProjectId) ?? projects[0];

  return (
    <div className="space-y-7">
      <section className="max-w-3xl">
        <p className="eyebrow">Independent developer tool</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
          Evidence first. Approval before every write.
        </h1>
        <p className="mt-3 text-base leading-7 text-slate-600">
          CodexForge turns a bug, feature request, or failed CI run into a reviewable plan, patch,
          and test evidence. GitHub branches and pull requests remain locked until you separately
          approve them.
        </p>
      </section>

      {projects.length === 0 ? (
        <ProjectEmptyState onConnected={(project) => setSelectedProjectId(project.id)} />
      ) : selectedProject ? (
        <>
          <ProjectSelector
            projects={projects}
            selectedProjectId={selectedProject.id}
            onSelect={setSelectedProjectId}
          />
          <WorkItemForm project={selectedProject} />
        </>
      ) : null}
    </div>
  );
}
