"use client";

import { useCallback, useEffect, useState } from "react";

import { CaseDetailSkeleton } from "@/components/cases/CaseDetailSkeleton";
import { CaseDetailView } from "@/components/cases/CaseDetailView";
import { mapCaseDetailApiToPageData } from "@/lib/cases/mapApi";
import { apiFetch } from "@/lib/api-auth";
import type { CaseDetailApi, CasePageData } from "@/types/case";

type CaseDetailClientProps = {
  caseId: string;
};

export function CaseDetailClient({ caseId }: CaseDetailClientProps) {
  const [data, setData] = useState<CasePageData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await apiFetch(`/api/v1/cases/${caseId}`);
    if (!res.ok) {
      const t = await res.text();
      setError(t || `Failed to load case (${res.status})`);
      setLoading(false);
      return;
    }
    const raw = (await res.json()) as CaseDetailApi;
    setData(mapCaseDetailApiToPageData(raw));
    setLoading(false);
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return <CaseDetailSkeleton />;
  }
  if (error || !data) {
    return (
      <div className="mx-auto max-w-lg rounded-lg border border-red-900/50 bg-red-950/20 p-6 text-center">
        <p className="text-sm font-medium text-red-200">Could not load case</p>
        <p className="mt-2 text-sm text-red-200/80">{error ?? "Unknown error"}</p>
        <button
          type="button"
          onClick={() => void load()}
          className="mt-4 rounded-md border border-shell-border px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-800/60"
        >
          Retry
        </button>
      </div>
    );
  }

  return <CaseDetailView data={data} />;
}
