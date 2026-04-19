import { QaConsole } from "@/components/QaConsole";

export default function QaPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
          QA Console
        </h1>
        <p className="mt-2 text-sm text-shell-muted">
          Review copilot sessions: transcripts, retrieval sources, tool traces, latency
          splits, and turn status. Deeper traces live in LangSmith when enabled server-side.
        </p>
      </div>
      <QaConsole />
    </div>
  );
}
