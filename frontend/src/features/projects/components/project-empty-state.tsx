import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { createIdempotencyKey } from "../../../shared/api/client";
import type { Project } from "../../../shared/api/contracts";
import { EmptyState } from "../../../shared/ui/async-state";
import { createProject } from "../api";
import { projectQueryKey } from "../hooks";

const connectionSchema = z.object({
  repositoryFullName: z
    .string()
    .trim()
    .regex(/^[^/\s]+\/[^/\s]+$/, "Use the GitHub repository format owner/repository."),
  defaultBranch: z
    .string()
    .trim()
    .max(255, "Keep the branch name under 255 characters.")
    .optional(),
});

type ConnectionValues = z.infer<typeof connectionSchema>;

export function ProjectEmptyState({ onConnected }: { onConnected: (project: Project) => void }) {
  const queryClient = useQueryClient();
  const form = useForm<ConnectionValues>({
    resolver: zodResolver(connectionSchema),
    defaultValues: { repositoryFullName: "", defaultBranch: "" },
  });
  const connectMutation = useMutation({
    mutationFn: createProject,
    onSuccess: async (project) => {
      await queryClient.invalidateQueries({ queryKey: projectQueryKey });
      onConnected(project);
    },
  });

  return (
    <EmptyState title="Connect a repository to begin">
      <p>
        Add a repository in <code>owner/repository</code> form to create a pending connection
        request. CodexForge cannot analyze it until the GitHub App verifies access and the server
        marks the connection active. This request does not create a branch, pull request, or
        repository change.
      </p>
      <form
        className="mt-5 grid max-w-xl gap-4"
        noValidate
        onSubmit={form.handleSubmit((values) =>
          connectMutation.mutate({
            repository_full_name: values.repositoryFullName.trim(),
            default_branch: values.defaultBranch?.trim() || undefined,
            idempotency_key: createIdempotencyKey(),
          }),
        )}
      >
        <div>
          <label className="field-label" htmlFor="repository-full-name">
            GitHub repository
          </label>
          <input
            id="repository-full-name"
            className="field-control mt-1"
            autoComplete="off"
            placeholder="owner/repository"
            aria-describedby="repository-full-name-error"
            {...form.register("repositoryFullName")}
          />
          {form.formState.errors.repositoryFullName ? (
            <p id="repository-full-name-error" className="field-error" role="alert">
              {form.formState.errors.repositoryFullName.message}
            </p>
          ) : null}
        </div>
        <div>
          <label className="field-label" htmlFor="repository-default-branch">
            Default branch <span className="font-normal text-slate-500">(optional)</span>
          </label>
          <input
            id="repository-default-branch"
            className="field-control mt-1"
            autoComplete="off"
            placeholder="main"
            {...form.register("defaultBranch")}
          />
        </div>
        {connectMutation.isError ? (
          <p className="field-error" role="alert">
            {connectMutation.error instanceof Error
              ? connectMutation.error.message
              : "The repository connection could not be created."}
          </p>
        ) : null}
        <div>
          <button type="submit" className="button-primary" disabled={connectMutation.isPending}>
            {connectMutation.isPending ? "Adding repository..." : "Add pending repository"}
          </button>
        </div>
      </form>
    </EmptyState>
  );
}
