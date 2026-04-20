import type { CaseActionItem } from "@/types/case";

const ACTION_STATUS: Record<
  CaseActionItem["status"],
  { label: string; className: string }
> = {
  todo: {
    label: "To do",
    className: "text-zinc-400 ring-zinc-600/80",
  },
  in_progress: {
    label: "In progress",
    className: "text-amber-200 ring-amber-800/80",
  },
  done: {
    label: "Done",
    className: "text-emerald-200 ring-emerald-800/80",
  },
};

type CaseActionItemsProps = {
  items: CaseActionItem[];
};

export function CaseActionItems({ items }: CaseActionItemsProps) {
  return (
    <section className="rounded-lg border border-shell-border bg-shell-panel p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium text-zinc-200">
          Recommended actions
        </h2>
        <span className="text-xs text-zinc-500">{items.length} items</span>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-zinc-500">
          No action items yet. They can be added manually or suggested from AI
          playbooks later.
        </p>
      ) : (
        <ul className="divide-y divide-shell-border">
          {items.map((item) => {
            const st = ACTION_STATUS[item.status];
            return (
              <li key={item.id} className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                <p className="min-w-0 flex-1 text-sm text-zinc-200">
                  {item.title}
                </p>
                <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
                  <span
                    className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ${st.className}`}
                  >
                    {st.label}
                  </span>
                  {item.owner ? (
                    <span className="text-xs text-zinc-500">{item.owner}</span>
                  ) : (
                    <span className="text-xs text-zinc-600">Unassigned</span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
