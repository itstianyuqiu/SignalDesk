import { QaConsole } from "@/components/QaConsole";

export default function QaPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
          QA Console
        </h1>
        <p className="mt-2 text-sm text-shell-muted">
          Review Copilot conversations in depth: what was said, which sources were used, tools invoked,
          timing, and quality signals—so you can validate answers before wider use.
        </p>
      </div>
      <QaConsole />
    </div>
  );
}
