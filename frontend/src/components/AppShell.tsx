"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { createBrowserSupabaseClient } from "@/lib/supabase/client";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/documents", label: "Documents" },
  { href: "/copilot", label: "Copilot" },
  { href: "/qa", label: "QA" },
] as const;

type AppShellProps = {
  userEmail: string | null;
  children: React.ReactNode;
};

export function AppShell({ userEmail, children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();

  async function handleSignOut() {
    const supabase = createBrowserSupabaseClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="hidden shrink-0 border-b border-shell-border bg-shell-panel md:block md:w-52 md:border-b-0 md:border-r">
        <div className="flex h-12 items-center border-b border-shell-border px-4">
          <span className="text-sm font-semibold tracking-tight text-zinc-100">
            Support Intelligence
          </span>
        </div>
        <nav className="flex flex-col gap-0.5 p-2 text-sm">
          {NAV_ITEMS.map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-md px-3 py-2 transition-colors ${
                  active
                    ? "bg-zinc-800/80 text-zinc-100"
                    : "text-shell-muted hover:bg-zinc-800/40 hover:text-zinc-200"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <nav className="flex gap-1 overflow-x-auto border-b border-shell-border bg-shell-panel px-2 py-2 md:hidden">
        {NAV_ITEMS.map((item) => {
          const active =
            pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`whitespace-nowrap rounded-md px-3 py-1.5 text-xs ${
                active
                  ? "bg-zinc-800/80 text-zinc-100"
                  : "text-shell-muted hover:text-zinc-200"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 items-center justify-between border-b border-shell-border bg-shell-bg px-4 md:px-6">
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">
              Signed in
            </p>
            <p className="truncate text-sm text-zinc-200">
              {userEmail ?? "—"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void handleSignOut()}
            className="rounded-md border border-shell-border px-3 py-1.5 text-xs font-medium text-zinc-200 transition-colors hover:bg-zinc-800/60"
          >
            Sign out
          </button>
        </header>
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
