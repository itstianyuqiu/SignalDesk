import { CopilotPanel } from "@/components/CopilotPanel";

export default function CopilotPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
          Copilot
        </h1>
        <p className="mt-2 text-sm text-shell-muted">
          Text RAG over your indexed documents: retrieval-backed answers with source excerpts and
          explicit low-confidence signaling when evidence is weak.
        </p>
      </div>
      <CopilotPanel />
    </div>
  );
}
