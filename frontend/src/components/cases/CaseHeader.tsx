import type { CaseDetailCore } from "@/types/case";

import {
  CaseCategoryBadge,
  CasePriorityBadge,
  CaseStatusBadge,
  formatCaseDate,
} from "@/components/cases/caseUi";

type CaseHeaderProps = {
  case: CaseDetailCore;
};

export function CaseHeader({ case: c }: CaseHeaderProps) {
  return (
    <div className="space-y-4 border-b border-shell-border pb-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-zinc-500">{c.caseKey}</span>
            <CaseStatusBadge status={c.status} />
            <CasePriorityBadge priority={c.priority} />
            <CaseCategoryBadge label={c.categoryLabel} />
          </div>
          <h1 className="text-xl font-semibold leading-snug tracking-tight text-zinc-100 md:text-2xl">
            {c.title}
          </h1>
        </div>
      </div>
      <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Case ID
          </dt>
          <dd className="mt-0.5 font-mono text-xs text-zinc-300">{c.id}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Created
          </dt>
          <dd className="mt-0.5 text-zinc-200">{formatCaseDate(c.createdAt)}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Updated
          </dt>
          <dd className="mt-0.5 text-zinc-200">{formatCaseDate(c.updatedAt)}</dd>
        </div>
      </dl>
    </div>
  );
}
