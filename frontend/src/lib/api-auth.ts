import { createBrowserSupabaseClient } from "@/lib/supabase/client";
import { getPublicApiBaseUrl } from "@/lib/env";

/**
 * Calls the FastAPI backend with the caller's Supabase access token when available.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const supabase = createBrowserSupabaseClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;

  const headers = new Headers(init.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const url = `${getPublicApiBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
  return fetch(url, { ...init, headers });
}
