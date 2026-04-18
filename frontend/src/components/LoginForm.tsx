"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { createBrowserSupabaseClient } from "@/lib/supabase/client";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const supabase = createBrowserSupabaseClient();
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (signInError) {
        setError(signInError.message);
        return;
      }
      router.push("/dashboard");
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={(e) => void onSubmit(e)}
      className="mx-auto w-full max-w-sm space-y-4 rounded-lg border border-shell-border bg-shell-panel p-6 shadow-sm"
    >
      <div>
        <h1 className="text-lg font-semibold text-zinc-100">Sign in</h1>
        <p className="mt-1 text-sm text-shell-muted">
          Use your Supabase Auth credentials.
        </p>
      </div>

      <div className="space-y-3">
        <label className="block text-xs font-medium text-zinc-400">
          Email
          <input
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-md border border-shell-border bg-shell-bg px-3 py-2 text-sm text-zinc-100 outline-none ring-shell-accent focus:ring-2"
          />
        </label>
        <label className="block text-xs font-medium text-zinc-400">
          Password
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-md border border-shell-border bg-shell-bg px-3 py-2 text-sm text-zinc-100 outline-none ring-shell-accent focus:ring-2"
          />
        </label>
      </div>

      {error ? (
        <p className="text-sm text-red-400" role="alert">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-md bg-zinc-100 px-3 py-2 text-sm font-medium text-zinc-900 transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Signing in…" : "Continue"}
      </button>
    </form>
  );
}
