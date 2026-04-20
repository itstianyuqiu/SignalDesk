"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type SVGProps } from "react";

import { apiFetch } from "@/lib/api-auth";

async function readApiErrorMessage(res: Response): Promise<string> {
  const text = await res.text();
  let msg = text || `HTTP ${res.status}`;
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    if (typeof parsed.detail === "string") {
      msg = parsed.detail;
    } else if (Array.isArray(parsed.detail)) {
      msg = parsed.detail.map((d) => JSON.stringify(d)).join("; ");
    }
  } catch {
    /* keep raw text */
  }
  return msg;
}

type DocumentRow = {
  id: string;
  title: string;
  status: string;
  updated_at: string;
};

type CopilotSessionRow = {
  id: string;
  title: string | null;
  updated_at: string;
};

type DashboardWorkspaceProps = {
  greetingName: string | null;
};

function IconChat(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} aria-hidden {...props}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.202 16.582 2.25 14.381 2.25 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
      />
    </svg>
  );
}

function IconFolder(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} aria-hidden {...props}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"
      />
    </svg>
  );
}

function IconMic(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} aria-hidden {...props}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"
      />
    </svg>
  );
}

function IconSpark(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} aria-hidden {...props}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z"
      />
    </svg>
  );
}

function formatWhen(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function DashboardWorkspace({ greetingName }: DashboardWorkspaceProps) {
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [sessions, setSessions] = useState<CopilotSessionRow[]>([]);
  const [docLoading, setDocLoading] = useState(true);
  const [sessLoading, setSessLoading] = useState(true);
  const [docError, setDocError] = useState<string | null>(null);
  const [sessError, setSessError] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    setDocLoading(true);
    setDocError(null);
    try {
      const res = await apiFetch("/api/v1/documents?limit=5");
      if (!res.ok) throw new Error(await readApiErrorMessage(res));
      const data = (await res.json()) as { items: DocumentRow[] };
      setDocuments(data.items ?? []);
    } catch (e) {
      setDocError(e instanceof Error ? e.message : "Could not load documents");
    } finally {
      setDocLoading(false);
    }
  }, []);

  const loadSessions = useCallback(async () => {
    setSessLoading(true);
    setSessError(null);
    try {
      const res = await apiFetch("/api/v1/copilot/sessions");
      if (!res.ok) throw new Error(await readApiErrorMessage(res));
      const data = (await res.json()) as CopilotSessionRow[];
      setSessions(Array.isArray(data) ? data.slice(0, 5) : []);
    } catch (e) {
      setSessError(e instanceof Error ? e.message : "Could not load sessions");
    } finally {
      setSessLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
    void loadSessions();
  }, [loadDocuments, loadSessions]);

  const headline =
    greetingName && greetingName.length > 0
      ? `Welcome back, ${greetingName}`
      : "Your AI workspace";

  return (
    <div className="mx-auto max-w-5xl space-y-12 pb-4">
      <section className="relative overflow-hidden rounded-2xl border border-shell-border/90 bg-gradient-to-br from-zinc-900/80 via-shell-panel to-[#121820] px-6 py-10 shadow-lg shadow-black/20 md:px-10 md:py-12">
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-shell-accent/10 blur-3xl"
          aria-hidden
        />
        <div className="relative max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-500">SignalDesk</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">{headline}</h1>
          <p className="mt-3 text-base leading-relaxed text-zinc-400 md:text-lg">
            Ground answers in your knowledge base, collaborate with Copilot, and keep every conversation
            and document in one place.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/copilot"
              className="inline-flex items-center justify-center rounded-lg bg-shell-accent px-5 py-2.5 text-sm font-semibold text-zinc-950 shadow-md transition hover:bg-[#79b8ff]"
            >
              Open Copilot
            </Link>
            <Link
              href="/documents"
              className="inline-flex items-center justify-center rounded-lg border border-shell-border bg-zinc-900/50 px-5 py-2.5 text-sm font-medium text-zinc-100 backdrop-blur transition hover:border-zinc-500 hover:bg-zinc-800/80"
            >
              Add documents
            </Link>
          </div>
        </div>
      </section>

      <section aria-labelledby="quick-actions-heading">
        <h2 id="quick-actions-heading" className="text-sm font-semibold text-zinc-200">
          Quick actions
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Link
            href="/copilot"
            className="group rounded-xl border border-shell-border bg-shell-panel/80 p-5 transition hover:border-shell-accent/40 hover:bg-zinc-900/40"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-shell-accent/15 text-shell-accent">
              <IconChat className="h-5 w-5" />
            </div>
            <p className="mt-4 font-medium text-zinc-100">New conversation</p>
            <p className="mt-1 text-sm text-shell-muted">Ask questions with retrieval-backed answers.</p>
            <span className="mt-3 inline-block text-sm font-medium text-shell-accent group-hover:underline">
              Start →
            </span>
          </Link>

          <Link
            href="/documents"
            className="group rounded-xl border border-shell-border bg-shell-panel/80 p-5 transition hover:border-shell-accent/40 hover:bg-zinc-900/40"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-400">
              <IconFolder className="h-5 w-5" />
            </div>
            <p className="mt-4 font-medium text-zinc-100">Knowledge library</p>
            <p className="mt-1 text-sm text-shell-muted">Upload PDFs and text to power search and answers.</p>
            <span className="mt-3 inline-block text-sm font-medium text-shell-accent group-hover:underline">
              Manage →
            </span>
          </Link>

          <Link
            href="/copilot"
            className="group rounded-xl border border-shell-border bg-shell-panel/80 p-5 transition hover:border-shell-accent/40 hover:bg-zinc-900/40"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-500/15 text-violet-300">
              <IconMic className="h-5 w-5" />
            </div>
            <p className="mt-4 font-medium text-zinc-100">Voice input</p>
            <p className="mt-1 text-sm text-shell-muted">Dictate in Copilot; we transcribe and send the text.</p>
            <span className="mt-3 inline-block text-sm font-medium text-shell-accent group-hover:underline">
              Try in Copilot →
            </span>
          </Link>

          <a
            href="#recent-sessions"
            className="group rounded-xl border border-shell-border bg-shell-panel/80 p-5 transition hover:border-shell-accent/40 hover:bg-zinc-900/40"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/15 text-amber-200">
              <IconSpark className="h-5 w-5" />
            </div>
            <p className="mt-4 font-medium text-zinc-100">Recent activity</p>
            <p className="mt-1 text-sm text-shell-muted">Jump to your latest documents and chats below.</p>
            <span className="mt-3 inline-block text-sm font-medium text-shell-accent group-hover:underline">
              Scroll ↓
            </span>
          </a>
        </div>
      </section>

      <div className="grid gap-8 lg:grid-cols-2">
        <section id="recent-documents" className="scroll-mt-8 rounded-xl border border-shell-border bg-shell-panel/60 p-5 md:p-6">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-zinc-100">Recent documents</h2>
            <Link href="/documents" className="text-sm font-medium text-shell-accent hover:underline">
              View all
            </Link>
          </div>
          <ul className="mt-4 divide-y divide-shell-border/70">
            {docLoading ? (
              <li className="py-6 text-sm text-shell-muted">Loading documents…</li>
            ) : docError ? (
              <li className="py-4 text-sm text-red-400">{docError}</li>
            ) : documents.length === 0 ? (
              <li className="py-6 text-sm text-shell-muted">
                No documents yet.{" "}
                <Link href="/documents" className="font-medium text-shell-accent hover:underline">
                  Upload your first file
                </Link>{" "}
                to ground Copilot in your content.
              </li>
            ) : (
              documents.map((d) => (
                <li key={d.id} className="flex flex-col gap-1 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-zinc-100">{d.title}</p>
                    <p className="mt-0.5 text-xs text-shell-muted">
                      {d.status} · {formatWhen(d.updated_at)}
                    </p>
                  </div>
                  <Link
                    href="/documents"
                    className="shrink-0 text-sm text-shell-accent hover:underline"
                  >
                    Library
                  </Link>
                </li>
              ))
            )}
          </ul>
        </section>

        <section id="recent-sessions" className="scroll-mt-8 rounded-xl border border-shell-border bg-shell-panel/60 p-5 md:p-6">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-zinc-100">Recent Copilot sessions</h2>
            <Link href="/copilot" className="text-sm font-medium text-shell-accent hover:underline">
              Open Copilot
            </Link>
          </div>
          <ul className="mt-4 divide-y divide-shell-border/70">
            {sessLoading ? (
              <li className="py-6 text-sm text-shell-muted">Loading sessions…</li>
            ) : sessError ? (
              <li className="py-4 text-sm text-red-400">{sessError}</li>
            ) : sessions.length === 0 ? (
              <li className="py-6 text-sm text-shell-muted">
                No conversations yet.{" "}
                <Link href="/copilot" className="font-medium text-shell-accent hover:underline">
                  Start a chat
                </Link>{" "}
                to see it listed here.
              </li>
            ) : (
              sessions.map((s) => (
                <li key={s.id} className="py-4 first:pt-0">
                  <Link
                    href={`/copilot?session=${encodeURIComponent(s.id)}`}
                    className="group block rounded-lg transition hover:bg-zinc-800/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-shell-accent"
                  >
                    <p className="font-medium text-zinc-100 group-hover:text-white">
                      {s.title?.trim() || "Untitled conversation"}
                    </p>
                    <p className="mt-0.5 text-xs text-shell-muted">Updated {formatWhen(s.updated_at)}</p>
                    <span className="mt-1 inline-block text-sm text-shell-accent opacity-0 transition group-hover:opacity-100">
                      Continue →
                    </span>
                  </Link>
                </li>
              ))
            )}
          </ul>
        </section>
      </div>

      <section aria-labelledby="capabilities-heading">
        <h2 id="capabilities-heading" className="text-sm font-semibold text-zinc-200">
          What you can do
        </h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-shell-border/80 bg-shell-bg/80 p-5">
            <h3 className="font-medium text-zinc-100">Answers tied to your sources</h3>
            <p className="mt-2 text-sm leading-relaxed text-shell-muted">
              Copilot retrieves from indexed documents and shows excerpts so you can verify every claim. When
              evidence is thin, we say so explicitly.
            </p>
          </div>
          <div className="rounded-xl border border-shell-border/80 bg-shell-bg/80 p-5">
            <h3 className="font-medium text-zinc-100">Structured support output</h3>
            <p className="mt-2 text-sm leading-relaxed text-shell-muted">
              Get suggested replies, action items, and escalation hints formatted for real support workflows—not
              generic chat filler.
            </p>
          </div>
          <div className="rounded-xl border border-shell-border/80 bg-shell-bg/80 p-5">
            <h3 className="font-medium text-zinc-100">Voice-friendly workflow</h3>
            <p className="mt-2 text-sm leading-relaxed text-shell-muted">
              Capture thoughts by voice in Copilot; transcription feeds the same pipeline as typed messages.
            </p>
          </div>
          <div className="rounded-xl border border-shell-border/80 bg-shell-bg/80 p-5">
            <h3 className="font-medium text-zinc-100">Session memory</h3>
            <p className="mt-2 text-sm leading-relaxed text-shell-muted">
              Conversations and documents stay organized so you can pick up where you left off without hunting
              through tabs.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
