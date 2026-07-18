import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";

import { createIdempotencyKey } from "../../../shared/api/client";
import type { Project } from "../../../shared/api/contracts";
import { createWorkItem } from "../api";
import { workItemFormSchema, type WorkItemFormValues } from "../schema";

interface WorkItemFormProps {
  project: Project;
}

export function WorkItemForm({ project }: WorkItemFormProps) {
  const navigate = useNavigate();
  const form = useForm<WorkItemFormValues>({
    resolver: zodResolver(workItemFormSchema),
    defaultValues: {
      kind: "feature",
      title: "",
      description: "",
      failedCiUrl: "",
    },
  });
  const kind = form.watch("kind");
  const submitMutation = useMutation({
    mutationFn: createWorkItem,
    onSuccess: ({ run }) => {
      navigate(`/runs/${run.id}`);
    },
  });

  const onSubmit = (values: WorkItemFormValues) => {
    submitMutation.mutate({
      project_id: project.id,
      kind: values.kind,
      title: values.title.trim(),
      description: values.description.trim(),
      failed_ci_url: values.failedCiUrl?.trim() || undefined,
      idempotency_key: createIdempotencyKey(),
    });
  };

  if (project.connection_status !== "active") {
    const isPending = project.connection_status === "pending";

    return (
      <section
        className="rounded-2xl border border-amber-200 bg-amber-50 p-5 shadow-panel sm:p-7"
        aria-labelledby="repository-verification-title"
      >
        <p className="eyebrow text-amber-800">Repository protection</p>
        <h2
          id="repository-verification-title"
          className="mt-1 text-xl font-semibold text-amber-950"
        >
          {isPending
            ? "GitHub App verification is pending"
            : "This repository connection is no longer active"}
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-amber-950" role="alert">
          {isPending
            ? "CodexForge cannot start repository analysis or create a work item until the GitHub App verifies access and the server marks this connection active."
            : "CodexForge cannot start repository analysis or create a work item while this connection is revoked. Reconnect and verify the GitHub App first."}
        </p>
      </section>
    );
  }

  return (
    <section
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-panel sm:p-7"
      aria-labelledby="new-work-item-title"
    >
      <div className="max-w-2xl">
        <p className="eyebrow">New work item</p>
        <h2 id="new-work-item-title" className="mt-1 text-xl font-semibold text-slate-950">
          What should CodexForge investigate?
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          The first outcome is a repository-evidenced plan. Nothing is written to GitHub at this
          stage.
        </p>
      </div>

      <form className="mt-6 grid gap-5" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <div>
          <label className="field-label" htmlFor="work-item-kind">
            Request type
          </label>
          <select id="work-item-kind" className="field-control mt-1" {...form.register("kind")}>
            <option value="feature">Feature request</option>
            <option value="bug">Bug report</option>
            <option value="failed_ci">Failed CI run</option>
          </select>
        </div>

        <div>
          <label className="field-label" htmlFor="work-item-title">
            Concise title
          </label>
          <input
            id="work-item-title"
            className="field-control mt-1"
            aria-describedby="work-item-title-help work-item-title-error"
            placeholder="For example: Add retry feedback for failed repository analysis"
            {...form.register("title")}
          />
          <p id="work-item-title-help" className="field-help">
            Include the user-visible outcome where possible.
          </p>
          {form.formState.errors.title ? (
            <p id="work-item-title-error" className="field-error" role="alert">
              {form.formState.errors.title.message}
            </p>
          ) : null}
        </div>

        <div>
          <label className="field-label" htmlFor="work-item-description">
            Context and expected outcome
          </label>
          <textarea
            id="work-item-description"
            className="field-control mt-1 min-h-36 resize-y"
            aria-describedby="work-item-description-help work-item-description-error"
            placeholder="Describe the current behavior, desired outcome, affected users, and any constraints."
            {...form.register("description")}
          />
          <p id="work-item-description-help" className="field-help">
            Add logs, reproduction details, or acceptance criteria. Repository content is treated as
            untrusted input.
          </p>
          {form.formState.errors.description ? (
            <p id="work-item-description-error" className="field-error" role="alert">
              {form.formState.errors.description.message}
            </p>
          ) : null}
        </div>

        {kind === "failed_ci" ? (
          <div>
            <label className="field-label" htmlFor="failed-ci-url">
              Failed CI run URL
            </label>
            <input
              id="failed-ci-url"
              className="field-control mt-1"
              inputMode="url"
              placeholder="https://github.com/owner/repository/actions/runs/..."
              {...form.register("failedCiUrl")}
            />
            {form.formState.errors.failedCiUrl ? (
              <p className="field-error" role="alert">
                {form.formState.errors.failedCiUrl.message}
              </p>
            ) : null}
          </div>
        ) : null}

        {submitMutation.isError ? (
          <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
            {submitMutation.error instanceof Error
              ? submitMutation.error.message
              : "The work item could not be created. Please retry."}
          </p>
        ) : null}

        <div className="flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-xl text-xs leading-5 text-slate-500">
            Submitting starts read-only repository analysis and creates an approval gate for the
            proposed plan.
          </p>
          <button
            type="submit"
            className="button-primary shrink-0"
            disabled={submitMutation.isPending}
          >
            {submitMutation.isPending ? "Creating work item…" : "Create work item"}
          </button>
        </div>
      </form>
    </section>
  );
}
