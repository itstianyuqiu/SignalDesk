"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  CaseCategoryBadge,
  CasePriorityBadge,
  CaseStatusBadge,
  formatCaseDate,
} from "@/components/cases/caseUi";
import { apiFetch } from "@/lib/api-auth";
import type { CaseListItem } from "@/types/case";

type CaseListResponse = {
  items: Array<{
    id: string;
    caseKey: string;
    title: string;
    status: string;
    priority: string;
    category: string | null;
    updatedAt: string;
  }>;
};

export default function CasesPage() {
  const [items, setItems] = useState<CaseListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await apiFetch("/api/v1/cases");
    if (!res.ok) {
      setError(await res.text());
      setLoading(false);
      return;
    }
    const data = (await res.json()) as CaseListResponse;
    setItems(
      data.items.map((c) => ({
        id: c.id,
        caseKey: c.caseKey,
        title: c.title,
        status: c.status as CaseListItem["status"],
        priority: c.priority as CaseListItem["priority"],
        categoryLabel: c.category?.trim() || "General",
        updatedAt: c.updatedAt,
      })),
    );
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl animate-pulse space-y-8">
        <div className="h-7 w-32 rounded bg-zinc-800" />
        <div className="h-72 rounded-lg border border-shell-border bg-shell-panel" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
          Cases
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-shell-muted">
          Tracked issues for support and operations — create a case from a Copilot
          conversation, then continue in the case workspace or reopen in Copilot with
          full context.
        </p>
      </div>

      {error ? (
        <div className="rounded-md border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      <section className="overflow-hidden rounded-lg border border-shell-border bg-shell-panel">
        <div className="border-b border-shell-border px-4 py-3">
          <h2 className="text-sm font-medium text-zinc-200">All cases</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-shell-border bg-shell-bg/50 text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-4 py-3 font-medium">Number</th>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Priority</th>
                <th className="px-4 py-3 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td
                    className="px-4 py-10 text-center text-shell-muted"
                    colSpan={6}
                  >
                    No cases yet. Start a Copilot chat, then use{" "}
                    <span className="text-zinc-400">Create case from conversation</span>{" "}
                    to track an issue.
                  </td>
                </tr>
              ) : (
                items.map((c) => (
                  <tr
                    key={c.id}
                    className="border-b border-shell-border/80 last:border-0 hover:bg-zinc-900/30"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-zinc-400">
                      <Link
                        href={`/cases/${c.id}`}
                        className="text-shell-accent hover:underline"
                      >
                        {c.caseKey}
                      </Link>
                    </td>
                    <td className="max-w-xs px-4 py-3">
                      <Link
                        href={`/cases/${c.id}`}
                        className="font-medium text-zinc-200 hover:text-white hover:underline"
                      >
                        {c.title}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <CaseCategoryBadge label={c.categoryLabel} />
                    </td>
                    <td className="px-4 py-3">
                      <CaseStatusBadge status={c.status} />
                    </td>
                    <td className="px-4 py-3">
                      <CasePriorityBadge priority={c.priority} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-zinc-500">
                      {formatCaseDate(c.updatedAt)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
