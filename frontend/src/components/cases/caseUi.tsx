import type { CasePriority, CaseStatus } from "@/types/case";

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  pending: "In progress",
  resolved: "Resolved",
  closed: "Closed",
};

export function formatCaseDate(iso: string): string {
  try {
    const d = new Date(iso);
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(d);
  } catch {
    return iso;
  }
}

export function formatCaseDateShort(iso: string): string {
  try {
    const d = new Date(iso);
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(d);
  } catch {
    return iso;
  }
}

const STATUS_STYLES: Record<
  CaseStatus,
  { label: string; className: string }
> = {
  open: {
    label: "Open",
    className: "bg-sky-950/50 text-sky-200 ring-sky-800/90",
  },
  pending: {
    label: "In progress",
    className: "bg-amber-950/50 text-amber-200 ring-amber-800/90",
  },
  resolved: {
    label: "Resolved",
    className: "bg-emerald-950/50 text-emerald-200 ring-emerald-800/90",
  },
  closed: {
    label: "Closed",
    className: "bg-zinc-800/90 text-zinc-300 ring-zinc-600/80",
  },
};

const PRIORITY_STYLES: Record<
  CasePriority,
  { label: string; className: string }
> = {
  low: {
    label: "Low",
    className: "bg-zinc-800/80 text-zinc-300 ring-zinc-600/80",
  },
  medium: {
    label: "Medium",
    className: "bg-blue-950/40 text-blue-200 ring-blue-800/70",
  },
  high: {
    label: "High",
    className: "bg-orange-950/50 text-orange-200 ring-orange-800/80",
  },
  critical: {
    label: "Critical",
    className: "bg-red-950/55 text-red-200 ring-red-800/85",
  },
};

export function CaseStatusBadge({ status }: { status: CaseStatus | string }) {
  const s =
    STATUS_STYLES[status as CaseStatus] ?? {
      label: STATUS_LABELS[status] ?? status,
      className: "bg-zinc-800 text-zinc-300 ring-zinc-700",
    };
  return (
    <span
      className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ${s.className}`}
    >
      {s.label}
    </span>
  );
}

export function CasePriorityBadge({ priority }: { priority: CasePriority }) {
  const p = PRIORITY_STYLES[priority];
  return (
    <span
      className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ${p.className}`}
    >
      {p.label}
    </span>
  );
}

export function CaseCategoryBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex rounded-md border border-shell-border bg-shell-bg px-2 py-0.5 text-xs text-zinc-300">
      {label}
    </span>
  );
}
