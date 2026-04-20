import type { CaseSummaryBlock } from "@/types/case";

import { formatCaseDate } from "@/components/cases/caseUi";

type CaseSummaryCardProps = {
  summary: CaseSummaryBlock;
};

function sourceLabel(source: CaseSummaryBlock["source"]): string {
  switch (source) {
    case "ai_draft":
      return "AI draft";
    case "manual":
      return "Manual";
    case "placeholder":
      return "Placeholder";
    default:
      return source;
  }
}

export function CaseSummaryCard({ summary }: CaseSummaryCardProps) {
  return (
    <section className="rounded-lg border border-shell-border bg-shell-panel p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-medium text-zinc-200">Case summary</h2>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md bg-zinc-800/80 px-2 py-0.5 text-xs text-zinc-400">
            {sourceLabel(summary.source)}
          </span>
          {summary.lastRefreshedAt ? (
            <span className="text-xs text-zinc-500">
              Refreshed {formatCaseDate(summary.lastRefreshedAt)}
            </span>
          ) : null}
        </div>
      </div>
      <p className="text-sm leading-relaxed text-zinc-300">{summary.text}</p>
      <p className="mt-3 text-xs text-zinc-500">
        Future: auto-refresh from Copilot, attachments, and CRM context; editable
        by assignee.
      </p>
    </section>
  );
}
