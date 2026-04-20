import { DashboardWorkspace } from "@/components/DashboardWorkspace";
import { createServerSupabaseClient } from "@/lib/supabase/server";

export default async function DashboardPage() {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const emailLocal = user?.email?.split("@")[0]?.trim();
  const greetingName =
    emailLocal && emailLocal.length > 0
      ? emailLocal.slice(0, 1).toUpperCase() + emailLocal.slice(1)
      : null;

  return <DashboardWorkspace greetingName={greetingName} />;
}
