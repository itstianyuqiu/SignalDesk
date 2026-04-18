/**
 * Browser-safe Supabase key: legacy "anon" JWT or new Publishable key (sb_publishable_...).
 * Never use the secret / service_role key in NEXT_PUBLIC_* variables.
 */
export function getSupabasePublicKey(): string | undefined {
  const fromAnon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim();
  const fromPublishable = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim();
  return fromAnon || fromPublishable || undefined;
}

export function getSupabaseUrl(): string | undefined {
  return process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() || undefined;
}
