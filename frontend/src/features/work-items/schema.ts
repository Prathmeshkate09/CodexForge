import { z } from "zod";

export const workItemFormSchema = z
  .object({
    kind: z.enum(["bug", "feature", "failed_ci"]),
    title: z
      .string()
      .trim()
      .min(8, "Use at least 8 characters so the request is actionable.")
      .max(180, "Keep the title under 180 characters."),
    description: z
      .string()
      .trim()
      .min(
        30,
        "Describe the expected outcome, scope, and useful context in at least 30 characters.",
      )
      .max(8_000, "Keep the description under 8,000 characters."),
    failedCiUrl: z.string().trim().url("Enter a valid CI run URL.").optional().or(z.literal("")),
  })
  .superRefine((value, context) => {
    if (value.kind === "failed_ci" && !value.failedCiUrl) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["failedCiUrl"],
        message: "A failed CI run URL is required for this request type.",
      });
    }
  });

export type WorkItemFormValues = z.infer<typeof workItemFormSchema>;
