"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { apiFetch } from "@/lib/api-auth";
import { useVoiceCapture } from "@/hooks/useVoiceCapture";

type SourceChunk = {
  chunk_id: string;
  document_id: string;
  title: string;
  score: number;
  excerpt: string;
};

type ToolRecord = {
  name?: string;
  call_id?: string;
  arguments?: string;
  result?: unknown;
};

type StructuredSupport = {
  answer?: string;
  action_items?: Array<{
    title: string;
    priority?: string;
    owner?: string | null;
  }>;
  escalation?: { level: string; rationale: string };
  support_reply_draft?: string | null;
};

type UiMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  weakEvidence?: boolean;
  sources?: SourceChunk[];
  toolCalls?: ToolRecord[];
  structured?: StructuredSupport | null;
};

type SessionInsights = {
  summary: string;
  action_items: string[];
  case_tags: string[];
  generated_at: string;
  model?: string | null;
};

type VoiceMeta = {
  mime_type: string;
  duration_sec: number;
  engine: string;
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
  const router = useRouter();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionInsights, setSessionInsights] = useState<SessionInsights | null>(null);
  const [pendingVoiceMeta, setPendingVoiceMeta] = useState<VoiceMeta | null>(null);
  /** Whisper language hint: English UI often sets `navigator.language` to en-* even when you speak Chinese. */
  const [speechLanguage, setSpeechLanguage] = useState<"auto" | "zh" | "en">("auto");
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const lastSendWasVoiceRef = useRef(false);
  const voice = useVoiceCapture();

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streaming]);

  const loadHistory = useCallback(async (sid: string) => {
    const [msgRes, sessRes] = await Promise.all([
      apiFetch(`/api/v1/copilot/sessions/${sid}/messages`),
      apiFetch(`/api/v1/copilot/sessions/${sid}`),
    ]);
    if (!msgRes.ok) {
      setSessionId(null);
      localStorage.removeItem(SESSION_KEY);
      return;
    }
    if (sessRes.ok) {
      const detail = (await sessRes.json()) as {
        metadata?: { session_insights?: SessionInsights };
      };
      setSessionInsights(detail.metadata?.session_insights ?? null);
    }
    const rows = (await msgRes.json()) as Array<{
      id: string;
      role: string;
      content: string;
      metadata?: {
        sources?: SourceChunk[];
        weak_evidence?: boolean;
        structured?: StructuredSupport;
        tools?: ToolRecord[];
      };
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
        structured: meta.structured ?? null,
        toolCalls: Array.isArray(meta.tools) ? meta.tools : [],
      });
    }
    setMessages(ui);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get("session");
    if (fromUrl) {
      setSessionId(fromUrl);
      localStorage.setItem(SESSION_KEY, fromUrl);
      void loadHistory(fromUrl);
      return;
    }
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
    setSessionInsights(null);
    setPendingVoiceMeta(null);
    setSpeechLanguage("auto");
    router.replace("/copilot");
  };

  const toggleVoiceCapture = async () => {
    setError(null);
    if (voice.status === "recording") {
      setTranscribing(true);
      try {
        const result = await voice.stopRecording();
        if (!result) {
          setTranscribing(false);
          return;
        }
        if (result.durationSec < 0.45) {
          setError(
            "Recording was too short. Hold Mic, speak a full sentence, then tap Stop.",
          );
          setTranscribing(false);
          return;
        }
        if (result.blob.size < 400) {
          setError("No usable audio captured. Check the microphone and try again.");
          setTranscribing(false);
          return;
        }
        // Near-silent clips cause Whisper to "hallucinate" stock subtitle lines (e.g. Amara.org).
        if (result.peakLevel >= 0 && result.peakLevel < 0.014) {
          setError(
            "Input level is too low (almost silent), so transcription may be wrong. In Windows: Settings → System → Sound, raise the input volume, pick the correct microphone, speak closer to it, and record 2–5 seconds.",
          );
          setTranscribing(false);
          return;
        }
        const fd = new FormData();
        fd.append("file", result.blob, "recording.webm");
        const langHint =
          speechLanguage === "auto"
            ? typeof navigator !== "undefined" && navigator.language
              ? navigator.language
              : ""
            : speechLanguage === "zh"
              ? "zh-CN"
              : "en-US";
        if (langHint) {
          fd.append("language", langHint);
        }
        const res = await apiFetch("/api/v1/copilot/voice/transcribe", {
          method: "POST",
          body: fd,
        });
        if (!res.ok) {
          const detail = await res.text();
          setError(detail || `Transcription failed (${res.status})`);
          setTranscribing(false);
          return;
        }
        const data = (await res.json()) as { text: string };
        setInput(data.text);
        setPendingVoiceMeta({
          mime_type: result.mimeType,
          duration_sec: result.durationSec,
          engine: "whisper-1",
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Transcription failed");
      } finally {
        setTranscribing(false);
      }
      return;
    }
    await voice.startRecording();
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading || streaming || transcribing) return;

    setError(null);
    const voiceMeta = pendingVoiceMeta;
    const useVoiceTurn = voiceMeta !== null;
    lastSendWasVoiceRef.current = useVoiceTurn;
    setInput("");
    setPendingVoiceMeta(null);
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
        toolCalls: [],
        structured: null,
      },
    ]);

    const res = await apiFetch("/api/v1/copilot/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        session_id: sessionId,
        input_mode: useVoiceTurn ? "voice" : "text",
        voice: useVoiceTurn
          ? {
              mime_type: voiceMeta.mime_type,
              duration_sec: voiceMeta.duration_sec,
              engine: voiceMeta.engine,
            }
          : undefined,
      }),
    });

    if (!res.ok) {
      lastSendWasVoiceRef.current = false;
      const detail = await res.text();
      setError(detail || `Request failed (${res.status})`);
      setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      setLoading(false);
      setStreaming(false);
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      lastSendWasVoiceRef.current = false;
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
            lastSendWasVoiceRef.current = false;
            setError(String(e.detail ?? "Stream error"));
            continue;
          }
          if (e.event === "meta") {
            const weak = Boolean(e.weak_evidence);
            const sources = Array.isArray(e.sources) ? (e.sources as SourceChunk[]) : [];
            const structured =
              e.structured && typeof e.structured === "object"
                ? (e.structured as StructuredSupport)
                : null;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, weakEvidence: weak, sources, structured }
                  : m,
              ),
            );
          } else if (e.event === "tool") {
            const rec: ToolRecord = {
              name: typeof e.name === "string" ? e.name : undefined,
              call_id: typeof e.call_id === "string" ? e.call_id : undefined,
              arguments: typeof e.arguments === "string" ? e.arguments : undefined,
              result: e.result,
            };
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, toolCalls: [...(m.toolCalls ?? []), rec] }
                  : m,
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
            const doneStructured =
              e.structured && typeof e.structured === "object"
                ? (e.structured as StructuredSupport)
                : null;
            const doneTools = Array.isArray(e.tool_trace)
              ? (e.tool_trace as ToolRecord[])
              : null;
            setMessages((prev) =>
              prev.map((m) => {
                if (m.id !== assistantId) return m;
                let next = m;
                if (finalText && !next.content.trim()) {
                  next = { ...next, content: finalText };
                }
                if (doneStructured) {
                  next = { ...next, structured: doneStructured };
                }
                if (doneTools && doneTools.length > 0) {
                  next = { ...next, toolCalls: doneTools };
                }
                return next;
              }),
            );
            if (lastSendWasVoiceRef.current) {
              lastSendWasVoiceRef.current = false;
              void (async () => {
                const insRes = await apiFetch(`/api/v1/copilot/sessions/${sid}/insights`, {
                  method: "POST",
                });
                if (insRes.ok) {
                  const ins = (await insRes.json()) as SessionInsights;
                  setSessionInsights(ins);
                }
              })();
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
            const sidTail = ev.session_id;
            setSessionId(sidTail);
            localStorage.setItem(SESSION_KEY, sidTail);
            const tailText = typeof ev.answer === "string" ? ev.answer : "";
            const tailStructured =
              ev.structured && typeof ev.structured === "object"
                ? (ev.structured as StructuredSupport)
                : null;
            const tailTools = Array.isArray(ev.tool_trace)
              ? (ev.tool_trace as ToolRecord[])
              : null;
            setMessages((prev) =>
              prev.map((m) => {
                if (m.id !== assistantId) return m;
                let next = m;
                if (tailText && !next.content.trim()) {
                  next = { ...next, content: tailText };
                }
                if (tailStructured) {
                  next = { ...next, structured: tailStructured };
                }
                if (tailTools && tailTools.length > 0) {
                  next = { ...next, toolCalls: tailTools };
                }
                return next;
              }),
            );
            if (lastSendWasVoiceRef.current) {
              lastSendWasVoiceRef.current = false;
              void (async () => {
                const insRes = await apiFetch(`/api/v1/copilot/sessions/${sidTail}/insights`, {
                  method: "POST",
                });
                if (insRes.ok) {
                  const ins = (await insRes.json()) as SessionInsights;
                  setSessionInsights(ins);
                }
              })();
            }
          }
        } catch {
          /* ignore */
        }
      }
    } catch (err) {
      lastSendWasVoiceRef.current = false;
      setError(err instanceof Error ? err.message : "Stream interrupted");
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="flex min-h-[60vh] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-shell-muted">
          The copilot calls tools (document search, case summary, action items, reply drafts) and
          returns a structured support summary. Tool results are shown below each answer. Voice uses
          your microphone, server-side Whisper transcription, then the same copilot workflow as
          typed messages.
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

      {voice.error ? (
        <div className="rounded-md border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-100">
          {voice.error}
        </div>
      ) : null}

      {sessionInsights ? (
        <div className="rounded-lg border border-emerald-900/50 bg-emerald-950/20 p-4 text-sm text-zinc-200">
          <p className="font-medium text-emerald-200/90">Session summary</p>
          <p className="mt-1 whitespace-pre-wrap text-zinc-300">{sessionInsights.summary}</p>
          {sessionInsights.action_items.length > 0 ? (
            <div className="mt-3">
              <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                Action items
              </p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-zinc-300">
                {sessionInsights.action_items.map((it, i) => (
                  <li key={`${it}-${i}`}>{it}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {sessionInsights.case_tags.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {sessionInsights.case_tags.map((t) => (
                <span
                  key={t}
                  className="rounded-full border border-emerald-900/40 bg-zinc-900/60 px-2 py-0.5 text-[11px] text-emerald-100/90"
                >
                  {t}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-1 flex-col rounded-lg border border-shell-border bg-shell-panel/40">
        <div className="max-h-[min(70vh,720px)] flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <p className="text-sm text-shell-muted">
              Ask for help with a case or your knowledge base. The assistant decides when to search
              documents or load case context; you will see each tool result for transparency.
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

              {m.role === "assistant" && (m.toolCalls?.length ?? 0) > 0 ? (
                <div className="w-full max-w-[95%] rounded-md border border-zinc-700/80 bg-zinc-900/40 p-3 text-xs md:max-w-[85%]">
                  <p className="font-medium text-zinc-300">Tool execution</p>
                  <p className="mt-0.5 text-[11px] text-zinc-500">
                    Arguments and raw results as returned by the backend (validated before use).
                  </p>
                  <ul className="mt-2 space-y-3">
                    {(m.toolCalls ?? []).map((t, idx) => (
                      <li key={`${t.call_id ?? idx}-${idx}`} className="rounded border border-zinc-800 bg-shell-bg/50 p-2">
                        <p className="font-mono text-[11px] text-emerald-300/90">
                          {t.name ?? "tool"}
                          {t.call_id ? (
                            <span className="text-zinc-500"> · {t.call_id.slice(0, 10)}…</span>
                          ) : null}
                        </p>
                        {t.arguments ? (
                          <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap break-words text-[11px] text-zinc-400">
                            {t.arguments}
                          </pre>
                        ) : null}
                        <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-words text-[11px] text-zinc-300">
                          {typeof t.result === "string"
                            ? t.result
                            : JSON.stringify(t.result, null, 2)}
                        </pre>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {m.role === "assistant" && m.structured ? (
                <div className="w-full max-w-[95%] space-y-2 rounded-md border border-indigo-900/50 bg-indigo-950/25 p-3 text-xs md:max-w-[85%]">
                  <p className="font-medium text-indigo-200/90">Structured output</p>
                  {m.structured.escalation ? (
                    <div className="rounded border border-indigo-900/40 bg-shell-bg/40 p-2">
                      <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                        Escalation
                      </p>
                      <p className="mt-1 text-[11px] text-indigo-100/90">
                        <span className="font-mono">{m.structured.escalation.level}</span>
                        {m.structured.escalation.rationale ? (
                          <span className="text-zinc-400"> — {m.structured.escalation.rationale}</span>
                        ) : null}
                      </p>
                    </div>
                  ) : null}
                  {m.structured.action_items && m.structured.action_items.length > 0 ? (
                    <div>
                      <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                        Action items
                      </p>
                      <ul className="mt-1 list-disc space-y-1 pl-4 text-zinc-300">
                        {m.structured.action_items.map((it, i) => (
                          <li key={`${it.title}-${i}`}>
                            <span className="font-medium text-zinc-200">{it.title}</span>
                            {it.priority ? (
                              <span className="ml-2 text-[10px] uppercase text-zinc-500">
                                {it.priority}
                              </span>
                            ) : null}
                            {it.owner ? (
                              <span className="ml-2 text-zinc-500">@{it.owner}</span>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {m.structured.support_reply_draft ? (
                    <div>
                      <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                        Support reply draft
                      </p>
                      <p className="mt-1 whitespace-pre-wrap text-zinc-300">
                        {m.structured.support_reply_draft}
                      </p>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {m.role === "assistant" &&
              m.sources &&
              m.sources.length > 0 &&
              m.content.length > 0 ? (
                <div className="w-full max-w-[95%] rounded-md border border-dashed border-shell-border bg-shell-panel/30 p-3 text-xs md:max-w-[85%]">
                  <p className="font-medium text-zinc-300">Sources (from search_documents)</p>
                  {m.weakEvidence ? (
                    <p className="mt-1 text-amber-200/90">
                      Low confidence: retrieval runs were marked weak or empty. Treat the answer as
                      tentative.
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
          <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-zinc-500">
            <label htmlFor="speech-lang" className="shrink-0">
              Transcription language
            </label>
            <select
              id="speech-lang"
              value={speechLanguage}
              onChange={(e) =>
                setSpeechLanguage(e.target.value as "auto" | "zh" | "en")
              }
              disabled={voice.status === "recording" || transcribing}
              className="rounded border border-shell-border bg-shell-bg px-2 py-1 text-zinc-200"
            >
              <option value="auto">Auto (browser locale)</option>
              <option value="zh">中文 (Chinese)</option>
              <option value="en">English</option>
            </select>
            <span className="text-zinc-600">
              If you speak Chinese but see wrong text, choose 中文.
            </span>
          </div>
          {pendingVoiceMeta ? (
            <p className="mb-2 text-xs text-emerald-200/85">
              Voice transcript (Whisper) — edit if needed, then Send.
            </p>
          ) : null}
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => {
                const v = e.target.value;
                setInput(v);
                if (!v.trim()) setPendingVoiceMeta(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void sendMessage();
                }
              }}
              rows={2}
              placeholder="Ask about your documents…"
              disabled={loading || streaming || transcribing || voice.status === "recording"}
              className="min-h-[44px] flex-1 resize-y rounded-md border border-shell-border bg-shell-bg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 disabled:opacity-50"
            />
            <button
              type="button"
              title={
                voice.status === "recording"
                  ? "Stop recording and transcribe"
                  : "Record voice (browser mic → Whisper)"
              }
              onClick={() => void toggleVoiceCapture()}
              disabled={
                loading ||
                streaming ||
                transcribing ||
                !voice.isSupported
              }
              className={`self-end rounded-md border px-3 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                voice.status === "recording"
                  ? "border-red-600/80 bg-red-950/50 text-red-100 animate-pulse"
                  : "border-shell-border text-zinc-200 hover:bg-zinc-800/60"
              }`}
            >
              {transcribing ? "…" : voice.status === "recording" ? "Stop" : "Mic"}
            </button>
            <button
              type="button"
              onClick={() => void sendMessage()}
              disabled={loading || streaming || transcribing || !input.trim()}
              className="self-end rounded-md bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              {streaming ? "Streaming…" : loading ? "…" : "Send"}
            </button>
          </div>
          {!voice.isSupported ? (
            <p className="mt-2 text-[11px] text-zinc-500">
              MediaRecorder / microphone not available in this environment.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
