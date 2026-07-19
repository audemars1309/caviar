/**
 * The single Supabase browser client (Phase 9A). Auth only: session
 * persistence + automatic token refresh are handled by supabase-js.
 * Application data ALWAYS flows through the Caviar backend API - the
 * frontend never queries the database directly.
 */
import { createClient } from "@supabase/supabase-js";

import { env } from "@/lib/env";

export const supabase = createClient(env.VITE_SUPABASE_URL, env.VITE_SUPABASE_ANON_KEY, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
