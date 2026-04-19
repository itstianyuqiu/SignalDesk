import { BackendStatus } from "@/components/BackendStatus";

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
          Dashboard
        </h1>
        <p className="mt-2 text-sm text-shell-muted">
          Phase 1 shell — documents and copilot routes are wired; AI features
          land in a later phase.
        </p>
      </div>
      <BackendStatus />
    </div>
  );
}
