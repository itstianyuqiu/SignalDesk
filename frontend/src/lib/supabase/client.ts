import { createBrowserClient } from "@supabase/ssr";

import { getSupabasePublicKey, getSupabaseUrl } from "@/lib/supabase/env";

export function createBrowserSupabaseClient() {
  const url = getSupabaseUrl();
  const key = getSupabasePublicKey();
  if (!url || !key) {
    throw new Error(
      "Missing Supabase env: set NEXT_PUBLIC_SUPABASE_URL and either " +
        "NEXT_PUBLIC_SUPABASE_ANON_KEY (anon / publishable) or NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY. " +
        "Do not use the secret (sb_secret_) key in the frontend.",
    );
  }
  return createBrowserClient(url, key);
}
