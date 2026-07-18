import type { Project } from "../../../shared/api/contracts";

interface ProjectSelectorProps {
  projects: Project[];
  selectedProjectId: string;
  onSelect: (projectId: string) => void;
}

export function ProjectSelector({ projects, selectedProjectId, onSelect }: ProjectSelectorProps) {
  const selectedProject = projects.find((project) => project.id === selectedProjectId);
  const connectionStatus = selectedProject?.connection_status ?? "pending";
  const statusLabel =
    connectionStatus === "active"
      ? "Active"
      : connectionStatus === "pending"
        ? "Verification pending"
        : "Revoked";
  const statusClass =
    connectionStatus === "active"
      ? "bg-emerald-100 text-emerald-800"
      : connectionStatus === "pending"
        ? "bg-amber-100 text-amber-900"
        : "bg-red-100 text-red-800";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-panel">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">Repository connection</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-950">Choose a workspace</h2>
          <p className="mt-1 text-sm text-slate-600">
            CodexForge can start work only after GitHub App verification marks the selected
            repository active.
          </p>
        </div>
        <div className="w-full sm:max-w-sm">
          <label className="field-label" htmlFor="project-selector">
            Repository
          </label>
          <select
            id="project-selector"
            className="field-control mt-1"
            value={selectedProjectId}
            onChange={(event) => onSelect(event.target.value)}
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.repository_full_name} / {project.default_branch} [
                {project.connection_status}]
              </option>
            ))}
          </select>
          <p className={`status-badge mt-3 ${statusClass}`} aria-live="polite">
            {statusLabel}
          </p>
        </div>
      </div>
    </div>
  );
}
