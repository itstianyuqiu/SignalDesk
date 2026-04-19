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
  try {
    return await fetch(url, { ...init, headers });
  } catch (e) {
    if (e instanceof TypeError) {
      const origin =
        typeof window !== "undefined" ? window.location.origin : "(unknown origin)";
      throw new Error(
        `Request to ${url} failed (${e.message}). If DevTools Network shows a status (e.g. 500) but the app still errors, the browser is often blocking the response: add this origin to backend CORS_ORIGINS — ${origin}. Otherwise check NEXT_PUBLIC_API_URL and that uvicorn is running.`,
      );
    }
    throw e;
  }
}
