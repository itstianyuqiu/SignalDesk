import { DocumentsPanel } from "@/components/DocumentsPanel";

export default function DocumentsPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
          Documents
        </h1>
        <p className="mt-2 text-sm text-shell-muted">
          Add text or PDFs so Copilot can search them and cite sources in answers.
        </p>
      </div>
      <DocumentsPanel />
    </div>
  );
}
