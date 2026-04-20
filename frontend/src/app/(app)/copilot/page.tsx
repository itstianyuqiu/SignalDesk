import { CopilotPanel } from "@/components/CopilotPanel";

export default function CopilotPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
          Copilot
        </h1>
        <p className="mt-2 text-sm text-shell-muted">
          Ask questions using your knowledge library. Replies include source excerpts, and Copilot tells you
          when it is not confident in the evidence.
        </p>
      </div>
      <CopilotPanel />
    </div>
  );
}
