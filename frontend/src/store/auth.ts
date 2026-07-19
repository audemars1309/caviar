/**
 * Authentication store (Phase 9A). Holds ONLY client auth state (who is
 * signed in, restoration status) - never server data and never tokens
 * (tokens live inside supabase-js; the API client reads them there).
 */
import { create } from "zustand";

import type { AuthStatus, AuthUser } from "@/types/auth";

interface AuthState {
  status: AuthStatus;
  user: AuthUser | null;
  setAuthenticated: (user: AuthUser) => void;
  setUnauthenticated: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  status: "loading",
  user: null,
  setAuthenticated: (user) => set({ status: "authenticated", user }),
  setUnauthenticated: () => set({ status: "unauthenticated", user: null }),
}));
