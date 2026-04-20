import Link from "next/link";

import { CaseActionItems } from "@/components/cases/CaseActionItems";
import { CaseHeader } from "@/components/cases/CaseHeader";
import { CaseSummaryCard } from "@/components/cases/CaseSummaryCard";
import { CaseTimeline } from "@/components/cases/CaseTimeline";
import { RelatedDocumentsCard } from "@/components/cases/RelatedDocumentsCard";
import { RelatedSessionsCard } from "@/components/cases/RelatedSessionsCard";
import type { CasePageData } from "@/types/case";

type CaseDetailViewProps = {
  data: CasePageData;
};

export function CaseDetailView({ data }: CaseDetailViewProps) {
  const { case: caseRow } = data;
  const copilotHref = `/copilot?caseId=${encodeURIComponent(caseRow.id)}${
    caseRow.createdFromSessionId
      ? `&session=${encodeURIComponent(caseRow.createdFromSessionId)}`
      : ""
  }`;

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Link
          href="/cases"
          className="text-sm text-shell-accent hover:underline"
        >
          ← Cases
        </Link>
        <Link
          href={copilotHref}
          className="inline-flex items-center justify-center rounded-md bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 transition-colors hover:bg-white"
        >
          Open in Copilot
        </Link>
      </div>

      <CaseHeader case={caseRow} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
        <div className="space-y-6">
          <CaseSummaryCard summary={data.summary} />
          <CaseActionItems items={data.actionItems} />
          <CaseTimeline events={data.timelineEvents} />
        </div>
        <aside className="space-y-6 lg:sticky lg:top-4">
          <RelatedSessionsCard
            caseId={caseRow.id}
            sessions={data.relatedSessions}
          />
          <RelatedDocumentsCard documents={data.relatedDocuments} />
        </aside>
      </div>
    </div>
  );
}
