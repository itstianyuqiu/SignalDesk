"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function CaseDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto max-w-lg rounded-lg border border-red-900/50 bg-red-950/20 p-6 text-center">
      <h1 className="text-lg font-semibold text-red-200">Could not load case</h1>
      <p className="mt-2 text-sm text-red-200/80">
        Something went wrong while loading this case. Try again, or return to the
        case list.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <button
          type="button"
          onClick={() => reset()}
          className="rounded-md border border-red-800/80 bg-red-950/40 px-4 py-2 text-sm font-medium text-red-100 hover:bg-red-950/60"
        >
          Retry
        </button>
        <Link
          href="/cases"
          className="rounded-md border border-shell-border px-4 py-2 text-sm font-medium text-zinc-200 hover:bg-zinc-800/60"
        >
          Back to cases
        </Link>
      </div>
    </div>
  );
}
