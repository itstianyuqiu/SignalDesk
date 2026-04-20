export default function CasesLoading() {
  return (
    <div className="mx-auto max-w-5xl animate-pulse space-y-8">
      <div>
        <div className="h-7 w-32 rounded bg-zinc-800" />
        <div className="mt-3 h-4 max-w-xl rounded bg-zinc-800/70" />
      </div>
      <div className="h-72 rounded-lg border border-shell-border bg-shell-panel">
        <div className="h-10 border-b border-shell-border bg-zinc-800/40" />
        <div className="space-y-2 p-4">
          <div className="h-8 rounded bg-zinc-800/50" />
          <div className="h-8 rounded bg-zinc-800/50" />
          <div className="h-8 rounded bg-zinc-800/50" />
        </div>
      </div>
    </div>
  );
}
