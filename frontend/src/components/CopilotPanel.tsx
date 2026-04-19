"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiFetch } from "@/lib/api-auth";

type SourceChunk = {
  chunk_id: string;
  document_id: string;
  title: string;
  score: number;
  excerpt: string;
};

type UiMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  weakEvidence?: boolean;
  sources?: SourceChunk[];
};

const SESSION_KEY = "signaldesk_copilot_session_id";

function parseSseBlocks(buffer: string): { events: unknown[]; rest: string } {
  // Normalize CRLF so blocks split reliably (some stacks emit \r\n\r\n).
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: unknown[] = [];
  for (const block of parts) {
    const line = block.trim();
    if (!line.startsWith("data:")) continue;
    const raw = line.slice(5).trim();
    if (!raw) continue;
    try {
      events.push(JSON.parse(raw));
    } catch {
      /* ignore malformed chunk */
    }
  }
  return { events, rest };
}

export function CopilotPanel() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streaming]);

  const loadHistory = useCallback(async (sid: string) => {
    const res = await apiFetch(`/api/v1/copilot/sessions/${sid}/messages`);
    if (!res.ok) {
      setSessionId(null);
      localStorage.removeItem(SESSION_KEY);
      return;
    }
    const rows = (await res.json()) as Array<{
      id: string;
      role: string;
      content: string;
      metadata?: { sources?: SourceChunk[]; weak_evidence?: boolean };
    }>;
    const ui: UiMessage[] = [];
    for (const m of rows) {
      if (m.role !== "user" && m.role !== "assistant") continue;
      const meta = m.metadata ?? {};
      ui.push({
        id: m.id,
        role: m.role,
        content: m.content,
        weakEvidence: meta.weak_evidence,
        sources: meta.sources,
      });
    }
    setMessages(ui);
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem(SESSION_KEY);
    if (stored) {
      setSessionId(stored);
      void loadHistory(stored);
    }
  }, [loadHistory]);

  const handleNewChat = () => {
    localStorage.removeItem(SESSION_KEY);
    setSessionId(null);
    setMessages([]);
    setError(null);
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading || streaming) return;

    setError(null);
    setInput("");
    setLoading(true);
    setStreaming(true);

    const userMsg: UiMessage = {
      id: `local-user-${Date.now()}`,
      role: "user",
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);

    const assistantId = `local-asst-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        sources: [],
        weakEvidence: false,
      },
    ]);

    const res = await apiFetch("/api/v1/copilot/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        session_id: sessionId,
      }),
    });

    if (!res.ok) {
      const detail = await res.text();
      setError(detail || `Request failed (${res.status})`);
      setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      setLoading(false);
      setStreaming(false);
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      setError("No response stream.");
      setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      setLoading(false);
      setStreaming(false);
      return;
    }

    setLoading(false);

    const decoder = new TextDecoder();
    let buf = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const { events, rest } = parseSseBlocks(buf);
        buf = rest;

        for (const ev of events) {
          if (!ev || typeof ev !== "object") continue;
          const e = ev as Record<string, unknown>;
          if (e.event === "error") {
            setError(String(e.detail ?? "Stream error"));
            continue;
          }
          if (e.event === "meta") {
            const weak = Boolean(e.weak_evidence);
            const sources = Array.isArray(e.sources) ? (e.sources as SourceChunk[]) : [];
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, weakEvidence: weak, sources } : m,
              ),
            );
          } else if (e.event === "delta" && typeof e.text === "string") {
            const delta = e.text;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: m.content + delta } : m,
              ),
            );
          } else if (e.event === "done" && typeof e.session_id === "string") {
            const sid = e.session_id;
            setSessionId(sid);
            localStorage.setItem(SESSION_KEY, sid);
            const finalText = typeof e.answer === "string" ? e.answer : "";
            if (finalText) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId && !m.content.trim()
                    ? { ...m, content: finalText }
                    : m,
                ),
              );
            }
          }
        }
      }
      const tail = buf.trim();
      if (tail.startsWith("data:")) {
        try {
          const raw = tail.slice(5).trim();
          const ev = JSON.parse(raw) as Record<string, unknown>;
          if (ev.event === "done" && typeof ev.session_id === "string") {
            setSessionId(ev.session_id);
            localStorage.setItem(SESSION_KEY, ev.session_id);
            const tailText = typeof ev.answer === "string" ? ev.answer : "";
            if (tailText) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId && !m.content.trim()
                    ? { ...m, content: tailText }
                    : m,
                ),
              );
            }
          }
        } catch {
          /* ignore */
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stream interrupted");
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="flex min-h-[60vh] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-shell-muted">
          Answers use your indexed documents only; sources below are retrieved passages, not
          free-form citations.
        </p>
        <button
          type="button"
          onClick={() => handleNewChat()}
          className="rounded-md border border-shell-border px-3 py-1.5 text-xs font-medium text-zinc-200 transition-colors hover:bg-zinc-800/60"
        >
          New chat
        </button>
      </div>

      {error ? (
        <div className="rounded-md border border-red-900/60 bg-red-950/40 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      <div className="flex flex-1 flex-col rounded-lg border border-shell-border bg-shell-panel/40">
        <div className="max-h-[min(70vh,720px)] flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <p className="text-sm text-shell-muted">
              Ask a question about your uploaded documents. The assistant retrieves relevant chunks
              and answers with explicit uncertainty when evidence is weak.
            </p>
          ) : null}

          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex flex-col gap-2 ${m.role === "user" ? "items-end" : "items-start"}`}
            >
              <div
                className={`max-w-[95%] rounded-lg px-3 py-2 text-sm leading-relaxed md:max-w-[85%] ${
                  m.role === "user"
                    ? "bg-zinc-800/90 text-zinc-100"
                    : "border border-shell-border bg-shell-bg/80 text-zinc-200"
                }`}
              >
                {m.role === "assistant" && streaming && m.content === "" ? (
                  <span className="text-shell-muted">Thinking…</span>
                ) : (
                  <div className="whitespace-pre-wrap">{m.content}</div>
                )}
              </div>

              {m.role === "assistant" &&
              m.sources &&
              m.sources.length > 0 &&
              m.content.length > 0 ? (
                <div className="w-full max-w-[95%] rounded-md border border-dashed border-shell-border bg-shell-panel/30 p-3 text-xs md:max-w-[85%]">
                  <p className="font-medium text-zinc-300">Sources (retrieved)</p>
                  {m.weakEvidence ? (
                    <p className="mt-1 text-amber-200/90">
                      Low confidence: best match score is below the configured threshold. Treat the
                      answer as tentative.
                    </p>
                  ) : null}
                  <ul className="mt-2 space-y-2">
                    {m.sources.map((s) => (
                      <li key={s.chunk_id} className="border-l-2 border-zinc-600 pl-2">
                        <p className="font-mono text-[11px] text-zinc-400">
                          {s.title}{" "}
                          <span className="text-zinc-500">
                            · score {s.score.toFixed(3)} · chunk {s.chunk_id.slice(0, 8)}…
                          </span>
                        </p>
                        <p className="mt-1 text-zinc-400">{s.excerpt}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {m.role === "assistant" && m.weakEvidence && (!m.sources || m.sources.length === 0) ? (
                <p className="max-w-[95%] text-xs text-amber-200/90 md:max-w-[85%]">
                  No relevant passages were retrieved; the answer may rely on general guidance only.
                </p>
              ) : null}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-shell-border p-3">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void sendMessage();
                }
              }}
              rows={2}
              placeholder="Ask about your documents…"
              disabled={loading || streaming}
              className="min-h-[44px] flex-1 resize-y rounded-md border border-shell-border bg-shell-bg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => void sendMessage()}
              disabled={loading || streaming || !input.trim()}
              className="self-end rounded-md bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              {streaming ? "Streaming…" : loading ? "…" : "Send"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
