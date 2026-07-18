import { workItemFormSchema } from "./schema";

describe("workItemFormSchema", () => {
  it("requires a CI run URL for failed CI work items", () => {
    const result = workItemFormSchema.safeParse({
      kind: "failed_ci",
      title: "Checkout workflow is failing",
      description: "The checkout workflow fails after dependency installation on the main branch.",
      failedCiUrl: "",
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.path).toEqual(["failedCiUrl"]);
    }
  });

  it("accepts an actionable feature request without a CI run", () => {
    const result = workItemFormSchema.safeParse({
      kind: "feature",
      title: "Expose repository evidence in plan review",
      description:
        "Show pinned source files and rationale beside every proposed plan step before approval.",
      failedCiUrl: "",
    });

    expect(result.success).toBe(true);
  });
});
