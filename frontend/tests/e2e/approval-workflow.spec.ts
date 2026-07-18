import { expect, test } from "@playwright/test";

test("blocks work-item creation while a manually entered repository is pending verification", async ({
  page,
}) => {
  let authorizationHeader: string | undefined;

  await page.route("**/api/v1/projects", async (route) => {
    authorizationHeader = route.request().headers().authorization;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "project-pending",
          repository_full_name: "owner/pending-repository",
          default_branch: "main",
          connection_status: "pending",
          created_at: "2026-07-18T12:00:00Z",
        },
      ]),
    });
  });

  await page.goto("/");

  await expect.poll(() => authorizationHeader).toBe("Bearer codexforge-playwright-local-token");
  await expect(page.getByText("Verification pending")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "GitHub App verification is pending" }),
  ).toBeVisible();
  await expect(
    page.getByText(/cannot start repository analysis or create a work item/),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Create work item" })).toHaveCount(0);
});

test("holds GitHub write authorization until the separately approved final gate", async ({
  page,
}) => {
  await page.route("**/api/v1/runs/run-123", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "run-123",
        project_id: "project-123",
        status: "plan_awaiting_approval",
        repository_commit_sha: "a1b2c3d4e5f67890",
        work_item: {
          id: "work-item-123",
          project_id: "project-123",
          kind: "bug",
          title: "Plan approval is required before any patch",
          description:
            "Verify that review controls remain locked until the evidence-backed plan receives approval.",
          created_at: "2026-07-18T12:00:00Z",
        },
        plan: {
          summary: "Inspect the approval state transition before patch generation.",
          steps: [
            {
              id: "step-1",
              title: "Validate the plan approval guard",
              rationale: "Patch generation must be server-gated by an explicit approval record.",
              affected_paths: ["backend/app/services/runs.py"],
            },
          ],
          evidence: [
            {
              path: "backend/app/services/runs.py",
              start_line: 42,
              commit_sha: "a1b2c3d4e5f67890",
              rationale: "The run service owns workflow state changes.",
            },
          ],
          risk_notes: ["An approval bypass could create unauthorized repository changes."],
          rollback_notes: ["Reject the plan and retain the repository snapshot for audit."],
        },
        plan_approval: { status: "pending" },
        pull_request_approval: { status: "pending" },
        timeline: [
          {
            id: "timeline-1",
            occurred_at: "2026-07-18T12:00:00Z",
            title: "Plan ready for review",
            detail: "Repository evidence has been collected.",
            state: "current",
          },
        ],
        patch_summary: null,
        changed_paths: [],
        check_evidence: [],
        pull_request: null,
        created_at: "2026-07-18T12:00:00Z",
        updated_at: "2026-07-18T12:01:00Z",
      }),
    });
  });

  await page.goto("/runs/run-123");

  await expect(page.getByRole("heading", { name: "Repository-evidenced plan" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve plan" })).toBeVisible();
  await expect(
    page.getByText(/Viewing this page cannot create a branch or pull request/),
  ).toBeVisible();
  await expect(page.getByText(/This action is locked until the plan is approved/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve branch and pull request creation" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Confirm and authorize GitHub write" }),
  ).toHaveCount(0);
});
