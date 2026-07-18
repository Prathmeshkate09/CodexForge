import type { ExecutionRun } from "../../../shared/api/contracts";

export function PatchReviewCard({ run }: { run: ExecutionRun }) {
  const hasPatch = Boolean(
    run.patch_summary || run.changed_paths.length || run.check_evidence.length,
  );

  return (
    <section className="panel" aria-labelledby="patch-title">
      <p className="eyebrow">Controlled review</p>
      <h2 id="patch-title" className="mt-1 text-xl font-semibold text-slate-950">
        Patch and test evidence
      </h2>
      {!hasPatch ? (
        <p className="mt-3 text-sm leading-6 text-slate-600">
          Patch generation and controlled checks remain unavailable until the plan is approved. This
          prevents an unreviewed request from modifying a connected repository.
        </p>
      ) : (
        <div className="mt-5 grid gap-6 lg:grid-cols-2">
          <div>
            <h3 className="section-title">Reviewable patch</h3>
            {run.patch_summary ? (
              <p className="mt-2 text-sm leading-6 text-slate-600">{run.patch_summary}</p>
            ) : null}
            {run.changed_paths.length > 0 ? (
              <ul className="mt-3 space-y-2" aria-label="Changed files">
                {run.changed_paths.map((path) => (
                  <li
                    key={path}
                    className="rounded-lg bg-slate-100 px-3 py-2 font-mono text-xs text-slate-800"
                  >
                    {path}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          <div>
            <h3 className="section-title">Controlled checks</h3>
            <ul className="mt-3 space-y-3">
              {run.check_evidence.map((check) => (
                <li key={check.command_label} className="rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-mono text-xs font-semibold text-slate-900">
                      {check.command_label}
                    </p>
                    <span
                      className={`status-badge ${check.outcome === "passed" ? "bg-emerald-100 text-emerald-800" : check.outcome === "failed" ? "bg-red-100 text-red-800" : "bg-slate-100 text-slate-700"}`}
                    >
                      {check.outcome === "not_run" ? "Not run" : check.outcome}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{check.summary}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </section>
  );
}
