import type { TimelineEvent } from "../../../shared/api/contracts";
import { formatDateTime } from "../../../shared/utils/formatters";

export function RunTimeline({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-slate-600">Progress will appear when analysis begins.</p>;
  }

  return (
    <ol className="space-y-0" aria-label="Run timeline">
      {events.map((event, index) => {
        const tone = {
          complete: "bg-emerald-500",
          current: "bg-indigo-600 ring-4 ring-indigo-100",
          pending: "bg-slate-300",
          failed: "bg-red-500",
        }[event.state];

        return (
          <li key={event.id} className="relative grid grid-cols-[1.5rem_1fr] gap-3 pb-6 last:pb-0">
            {index < events.length - 1 ? (
              <span
                className="absolute left-3 top-6 h-[calc(100%-0.35rem)] w-px bg-slate-200"
                aria-hidden="true"
              />
            ) : null}
            <span className={`mt-1.5 h-3 w-3 rounded-full ${tone}`} aria-hidden="true" />
            <div aria-current={event.state === "current" ? "step" : undefined}>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <p className="text-sm font-semibold text-slate-900">{event.title}</p>
                <time className="text-xs text-slate-500" dateTime={event.occurred_at}>
                  {formatDateTime(event.occurred_at)}
                </time>
              </div>
              <p className="mt-1 text-sm leading-6 text-slate-600">{event.detail}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
