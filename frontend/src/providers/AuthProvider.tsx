import { useEffect, type ReactNode } from "react";

import { supabase } from "@/lib/supabase";
import { useAuthStore } from "@/store/auth";
import { useUserStore } from "@/store/user";

/**
 * Session restoration + auth event subscription (Phase 9A). On mount,
 * the persisted Supabase session is restored (status stays "loading"
 * until resolved - guards hold instead of flashing the login page).
 * Every subsequent auth event (sign-in, sign-out, token refresh) flows
 * through onAuthStateChange into the auth store, which is the single
 * client-side source of truth for "who is signed in".
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const setAuthenticated = useAuthStore((state) => state.setAuthenticated);
  const setUnauthenticated = useAuthStore((state) => state.setUnauthenticated);
  const resetUser = useUserStore((state) => state.reset);

  useEffect(() => {
    let cancelled = false;

    void supabase.auth.getSession().then(({ data }) => {
      if (cancelled) return;
      const user = data.session?.user;
      if (user) setAuthenticated({ id: user.id, email: user.email ?? null });
      else setUnauthenticated();
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      const user = session?.user;
      if (user) {
        setAuthenticated({ id: user.id, email: user.email ?? null });
      } else {
        setUnauthenticated();
        resetUser();
      }
    });

    return () => {
      cancelled = true;
      subscription.subscription.unsubscribe();
    };
  }, [setAuthenticated, setUnauthenticated, resetUser]);

  return children;
}
