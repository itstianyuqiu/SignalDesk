export function CaseDetailSkeleton() {
  return (
    <div className="mx-auto max-w-6xl animate-pulse space-y-6">
      <div className="h-4 w-24 rounded bg-zinc-800" />
      <div className="space-y-3 border-b border-shell-border pb-6">
        <div className="flex gap-2">
          <div className="h-5 w-20 rounded bg-zinc-800" />
          <div className="h-5 w-24 rounded bg-zinc-800" />
          <div className="h-5 w-16 rounded bg-zinc-800" />
        </div>
        <div className="h-8 max-w-xl rounded bg-zinc-800" />
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="h-10 rounded bg-zinc-800/80" />
          <div className="h-10 rounded bg-zinc-800/80" />
          <div className="h-10 rounded bg-zinc-800/80" />
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <div className="h-36 rounded-lg bg-zinc-800/60" />
          <div className="h-48 rounded-lg bg-zinc-800/60" />
          <div className="h-64 rounded-lg bg-zinc-800/60" />
        </div>
        <div className="space-y-6">
          <div className="h-40 rounded-lg bg-zinc-800/60" />
          <div className="h-40 rounded-lg bg-zinc-800/60" />
        </div>
      </div>
    </div>
  );
}
