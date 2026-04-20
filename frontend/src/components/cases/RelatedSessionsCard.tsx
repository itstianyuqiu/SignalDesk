import Link from "next/link";

import type { RelatedSession } from "@/types/case";

import { formatCaseDate } from "@/components/cases/caseUi";

type RelatedSessionsCardProps = {
  caseId: string;
  sessions: RelatedSession[];
};

function sessionHref(caseId: string, sessionId: string): string {
  const q = new URLSearchParams({ caseId, session: sessionId });
  return `/copilot?${q.toString()}`;
}

export function RelatedSessionsCard({
  caseId,
  sessions,
}: RelatedSessionsCardProps) {
  return (
    <section className="rounded-lg border border-shell-border bg-shell-panel p-4">
      <h2 className="mb-3 text-sm font-medium text-zinc-200">
        Related sessions
      </h2>
      {sessions.length === 0 ? (
        <div className="rounded-md border border-dashed border-shell-border bg-shell-bg/50 px-3 py-6 text-center">
          <p className="text-sm text-zinc-500">No linked conversations yet.</p>
          <p className="mt-1 text-xs text-zinc-600">
            Copilot threads and other channels will appear here when associated
            with this case.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {sessions.map((s) => (
            <li key={s.id}>
              <Link
                href={sessionHref(caseId, s.id)}
                className="block rounded-md border border-shell-border bg-shell-bg/40 p-3 transition-colors hover:border-zinc-600 hover:bg-zinc-900/40"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium text-zinc-200">
                    {s.title}
                  </span>
                  <span className="shrink-0 text-xs text-zinc-500">
                    {formatCaseDate(s.updatedAt)}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-zinc-500">
                  {s.preview}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
