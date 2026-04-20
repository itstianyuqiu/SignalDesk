import type { CaseTimelineEvent } from "@/types/case";

import { formatCaseDate } from "@/components/cases/caseUi";

type CaseTimelineProps = {
  events: CaseTimelineEvent[];
};

function dotClass(kind: CaseTimelineEvent["kind"]): string {
  switch (kind) {
    case "created":
      return "bg-sky-500";
    case "summary_updated":
      return "bg-violet-500";
    case "actions_generated":
      return "bg-amber-500";
    case "note":
      return "bg-zinc-500";
    case "status_change":
      return "bg-emerald-500";
    case "escalation":
      return "bg-red-500";
    default:
      return "bg-zinc-500";
  }
}

export function CaseTimeline({ events }: CaseTimelineProps) {
  const sorted = [...events].sort(
    (a, b) => new Date(b.at).getTime() - new Date(a.at).getTime(),
  );

  return (
    <section className="rounded-lg border border-shell-border bg-shell-panel p-4">
      <h2 className="mb-4 text-sm font-medium text-zinc-200">
        Activity & notes
      </h2>
      {sorted.length === 0 ? (
        <p className="text-sm text-zinc-500">No activity recorded yet.</p>
      ) : (
        <ol className="relative ml-1 list-none border-l border-shell-border">
          {sorted.map((ev) => (
            <li key={ev.id} className="relative pb-6 pl-5 last:pb-0">
              <span
                className={`absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-shell-panel ${dotClass(ev.kind)}`}
                aria-hidden
              />
              <div>
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="text-sm font-medium text-zinc-200">
                    {ev.label}
                  </span>
                  <time
                    className="text-xs text-zinc-500"
                    dateTime={ev.at}
                  >
                    {formatCaseDate(ev.at)}
                  </time>
                </div>
                {ev.actor ? (
                  <p className="text-xs text-zinc-500">{ev.actor}</p>
                ) : null}
                {ev.detail ? (
                  <p className="mt-1 text-sm text-zinc-400">{ev.detail}</p>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      )}
      <p className="mt-4 border-t border-shell-border pt-3 text-xs text-zinc-600">
        Future: editable notes, QA trace links, and automated entries from
        workflows.
      </p>
    </section>
  );
}
