"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api-auth";

type QASession = {
  id: string;
  title: string | null;
  updated_at: string;
  created_at: string;
  message_count: number;
};

type QAMessage = {
  id: string;
  role: string;
  content: string;
  position: number;
  created_at: string;
  metadata?: Record<string, unknown>;
};

type SourceRow = {
  chunk_id?: string;
  document_id?: string;
  title?: string;
  score?: number;
  excerpt?: string;
};

type ToolRow = {
  name?: string;
  call_id?: string;
  arguments?: string;
  result?: unknown;
};

type Observability = {
  status?: string;
  langsmith?: { project?: string | null; tracing_enabled?: boolean };
  latency_ms?: Record<string, number>;
  cost?: { estimated_usd?: number | null; note?: string };
};

function StatusBadge({ status }: { status?: string }) {
  const s = status ?? "unknown";
  const cls =
    s === "ok"
      ? "bg-emerald-950/60 text-emerald-200 ring-emerald-800/80"
      : s === "warning"
        ? "bg-amber-950/60 text-amber-200 ring-amber-800/80"
        : s === "error"
          ? "bg-red-950/60 text-red-200 ring-red-800/80"
          : "bg-zinc-800 text-zinc-300 ring-zinc-700";
  return (
    <span
      className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ${cls}`}
    >
      {s}
    </span>
  );
}

export function QaConsole() {
  const [sessions, setSessions] = useState<QASession[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<QAMessage[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    setLoadingList(true);
    setError(null);
    const res = await apiFetch("/api/v1/qa/copilot-sessions");
    if (!res.ok) {
      setError(`Failed to load sessions (${res.status})`);
      setLoadingList(false);
      return;
    }
    const data = (await res.json()) as QASession[];
    setSessions(data);
    setLoadingList(false);
  }, []);

  const loadDetail = useCallback(async (sid: string) => {
    setLoadingDetail(true);
    setError(null);
    const res = await apiFetch(`/api/v1/qa/copilot-sessions/${sid}`);
    if (!res.ok) {
      setError(`Failed to load session (${res.status})`);
      setLoadingDetail(false);
      return;
    }
    const data = (await res.json()) as { messages: QAMessage[] };
    setMessages(data.messages);
    setLoadingDetail(false);
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (selectedId) void loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,280px)_1fr]">
      <section className="rounded-lg border border-shell-border bg-shell-panel p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 className="text-sm font-medium text-zinc-200">Sessions</h2>
          <button
            type="button"
            onClick={() => void loadSessions()}
            className="text-xs text-zinc-400 hover:text-zinc-200"
          >
            Refresh
          </button>
        </div>
        {loadingList ? (
          <p className="text-xs text-shell-muted">Loading…</p>
        ) : sessions.length === 0 ? (
          <p className="text-xs text-shell-muted">No copilot sessions yet.</p>
        ) : (
          <ul className="max-h-[70vh] space-y-1 overflow-y-auto pr-1">
            {sessions.map((s) => {
              const active = selectedId === s.id;
              return (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(s.id)}
                    className={`w-full rounded-md px-2 py-2 text-left text-xs transition-colors ${
                      active
                        ? "bg-zinc-800/90 text-zinc-100"
                        : "text-zinc-300 hover:bg-zinc-800/50"
                    }`}
                  >
                    <span className="line-clamp-2 font-medium">
                      {s.title ?? "Untitled"}
                    </span>
                    <span className="mt-0.5 block text-[10px] text-zinc-500">
                      {s.message_count} msgs ·{" "}
                      {new Date(s.updated_at).toLocaleString()}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="min-w-0 space-y-4">
        {error ? (
          <p className="text-sm text-red-300">{error}</p>
        ) : null}
        {!selectedId ? (
          <p className="text-sm text-shell-muted">Select a session to inspect.</p>
        ) : loadingDetail ? (
          <p className="text-sm text-shell-muted">Loading transcript…</p>
        ) : (
          <div className="space-y-6">
            {messages.map((m) => {
              const meta = (m.metadata ?? {}) as Record<string, unknown>;
              const sources = (meta.sources as SourceRow[] | undefined) ?? [];
              const tools = (meta.tools as ToolRow[] | undefined) ?? [];
              const obs = meta.observability as Observability | undefined;
              const structured = meta.structured as Record<string, unknown> | undefined;

              if (m.role !== "user" && m.role !== "assistant") {
                return null;
              }

              return (
                <article
                  key={m.id}
                  className="rounded-lg border border-shell-border bg-shell-panel/40 p-4"
                >
                  <header className="mb-3 flex flex-wrap items-center gap-2 border-b border-shell-border pb-2">
                    <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                      {m.role}
                    </span>
                    <span className="text-[10px] text-zinc-500">
                      #{m.position} · {new Date(m.created_at).toLocaleString()}
                    </span>
                    {m.role === "assistant" && obs?.status ? (
                      <StatusBadge status={obs.status} />
                    ) : null}
                  </header>

                  <div className="whitespace-pre-wrap text-sm text-zinc-200">
                    {m.content}
                  </div>

                  {m.role === "assistant" && obs ? (
                    <div className="mt-4 grid gap-3 rounded-md border border-zinc-800/80 bg-zinc-950/40 p-3 text-xs md:grid-cols-2">
                      <div>
                        <h3 className="mb-1 font-medium text-zinc-400">Latency (ms)</h3>
                        <dl className="space-y-0.5 text-zinc-300">
                          {obs.latency_ms
                            ? Object.entries(obs.latency_ms).map(([k, v]) => (
                                <div key={k} className="flex justify-between gap-4">
                                  <dt className="text-zinc-500">{k}</dt>
                                  <dd className="font-mono text-zinc-200">{v}</dd>
                                </div>
                              ))
                            : (
                                <p className="text-zinc-500">—</p>
                              )}
                        </dl>
                      </div>
                      <div>
                        <h3 className="mb-1 font-medium text-zinc-400">Cost / LangSmith</h3>
                        <p className="text-zinc-300">
                          est. USD:{" "}
                          <span className="font-mono">
                            {obs.cost?.estimated_usd ?? "—"}
                          </span>
                        </p>
                        <p className="mt-1 text-[11px] text-zinc-500">
                          {obs.cost?.note ?? ""}
                        </p>
                        <p className="mt-2 text-zinc-300">
                          project:{" "}
                          <span className="font-mono">
                            {obs.langsmith?.project ?? "—"}
                          </span>
                          {obs.langsmith?.tracing_enabled ? " · tracing on" : ""}
                        </p>
                      </div>
                    </div>
                  ) : null}

                  {m.role === "assistant" && sources.length > 0 ? (
                    <div className="mt-4">
                      <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
                        Retrieved sources
                      </h3>
                      <ul className="space-y-2">
                        {sources.map((src, i) => (
                          <li
                            key={`${src.chunk_id ?? i}`}
                            className="rounded border border-zinc-800/80 bg-zinc-950/30 p-2 text-xs"
                          >
                            <p className="font-medium text-zinc-200">
                              {src.title ?? "Untitled"}{" "}
                              <span className="text-zinc-500">
                                ({src.score?.toFixed?.(3) ?? "—"})
                              </span>
                            </p>
                            <p className="mt-1 text-zinc-400">{src.excerpt}</p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {m.role === "assistant" && tools.length > 0 ? (
                    <div className="mt-4">
                      <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
                        Tool calls
                      </h3>
                      <ul className="space-y-2 font-mono text-[11px] text-zinc-300">
                        {tools.map((t, i) => (
                          <li
                            key={t.call_id ?? `${t.name}-${i}`}
                            className="rounded border border-zinc-800/80 bg-zinc-950/30 p-2"
                          >
                            <span className="text-emerald-400/90">{t.name}</span>
                            {t.arguments ? (
                              <pre className="mt-1 max-h-28 overflow-auto whitespace-pre-wrap text-zinc-500">
                                {t.arguments}
                              </pre>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {m.role === "assistant" && structured ? (
                    <details className="mt-4 text-xs">
                      <summary className="cursor-pointer text-zinc-400">
                        Structured output (JSON)
                      </summary>
                      <pre className="mt-2 max-h-48 overflow-auto rounded border border-zinc-800/80 bg-zinc-950/50 p-2 text-[11px] text-zinc-400">
                        {JSON.stringify(structured, null, 2)}
                      </pre>
                    </details>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
