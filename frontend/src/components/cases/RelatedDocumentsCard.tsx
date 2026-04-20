import Link from "next/link";

import type { RelatedDocument } from "@/types/case";

import { formatCaseDateShort } from "@/components/cases/caseUi";

type RelatedDocumentsCardProps = {
  documents: RelatedDocument[];
};

function docHref(documentId: string): string {
  return `/documents?highlight=${encodeURIComponent(documentId)}`;
}

export function RelatedDocumentsCard({ documents }: RelatedDocumentsCardProps) {
  return (
    <section className="rounded-lg border border-shell-border bg-shell-panel p-4">
      <h2 className="mb-3 text-sm font-medium text-zinc-200">
        Related documents
      </h2>
      {documents.length === 0 ? (
        <div className="rounded-md border border-dashed border-shell-border bg-shell-bg/50 px-3 py-6 text-center">
          <p className="text-sm text-zinc-500">No documents linked.</p>
          <p className="mt-1 text-xs text-zinc-600">
            Attach knowledge-base files or pin citations from Copilot when
            available.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-shell-border">
          {documents.map((d) => (
            <li key={d.id} className="py-2 first:pt-0 last:pb-0">
              <Link
                href={docHref(d.id)}
                className="group flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between"
              >
                <span className="text-sm font-medium text-shell-accent group-hover:underline">
                  {d.title}
                </span>
                <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                  <span className="rounded bg-zinc-800/80 px-1.5 py-0.5 text-zinc-400">
                    {d.tag}
                  </span>
                  <span>Updated {formatCaseDateShort(d.updatedAt)}</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
