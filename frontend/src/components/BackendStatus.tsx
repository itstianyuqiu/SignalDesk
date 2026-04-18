"use client";

import { useEffect, useState } from "react";

import { ApiError, fetchHealth, type HealthResponse } from "@/lib/api";
import { getPublicApiBaseUrl } from "@/lib/env";

type LoadState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; data: HealthResponse }
  | { status: "error"; message: string };

export function BackendStatus() {
  const [state, setState] = useState<LoadState>({ status: "idle" });

  useEffect(() => {
    const baseUrl = getPublicApiBaseUrl();
    let cancelled = false;

    async function run() {
      setState({ status: "loading" });
      try {
        const data = await fetchHealth(baseUrl);
        if (!cancelled) setState({ status: "ok", data });
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Unknown error";
        if (!cancelled) setState({ status: "error", message });
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="rounded-lg border border-shell-border bg-shell-panel p-5">
      <h2 className="text-sm font-semibold text-zinc-100">Backend connectivity</h2>
      <p className="mt-1 text-sm text-shell-muted">
        Live check against <code className="font-mono text-shell-accent">{`${getPublicApiBaseUrl()}/health`}</code>
      </p>
      <div className="mt-4 text-sm">
        {state.status === "idle" || state.status === "loading" ? (
          <p className="text-shell-muted">Checking API…</p>
        ) : state.status === "error" ? (
          <p className="text-red-400">{state.message}</p>
        ) : (
          <dl className="grid gap-2 sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-zinc-500">Status</dt>
              <dd className="font-mono text-emerald-400">{state.data.status}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-zinc-500">Service</dt>
              <dd className="font-mono text-zinc-200">{state.data.service}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-zinc-500">Environment</dt>
              <dd className="font-mono text-zinc-200">{state.data.environment}</dd>
            </div>
          </dl>
        )}
      </div>
    </section>
  );
}
