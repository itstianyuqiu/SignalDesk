import { DocumentsPanel } from "@/components/DocumentsPanel";

export default function DocumentsPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
          Documents
        </h1>
        <p className="mt-2 text-sm text-shell-muted">
          Upload text or PDFs for chunking, embeddings (OpenAI), and pgvector storage. Retrieval API:{" "}
          <code className="font-mono text-xs text-shell-accent">POST /api/v1/retrieve</code>.
        </p>
      </div>
      <DocumentsPanel />
    </div>
  );
}
