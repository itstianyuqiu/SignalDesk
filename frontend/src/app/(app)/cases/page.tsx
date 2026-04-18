export default function CasesPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-10">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
          Cases & sessions
        </h1>
        <p className="mt-2 text-sm text-shell-muted">
          Support cases and conversation sessions map to{" "}
          <code className="font-mono text-xs text-shell-accent">cases</code> and{" "}
          <code className="font-mono text-xs text-shell-accent">sessions</code>{" "}
          in Postgres; messages store transcript and future tool traces.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-zinc-200">Cases</h2>
        <div className="overflow-hidden rounded-lg border border-shell-border">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-shell-border bg-shell-panel text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-4 py-3 font-medium">Number</th>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="px-4 py-6 text-shell-muted" colSpan={3}>
                  No cases yet. API:{" "}
                  <code className="font-mono text-xs text-zinc-400">
                    GET /api/v1/cases
                  </code>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-zinc-200">Sessions</h2>
        <div className="overflow-hidden rounded-lg border border-shell-border">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-shell-border bg-shell-panel text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Channel</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="px-4 py-6 text-shell-muted" colSpan={3}>
                  No sessions yet. API:{" "}
                  <code className="font-mono text-xs text-zinc-400">
                    GET /api/v1/sessions
                  </code>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
