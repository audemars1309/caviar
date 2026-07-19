/**
 * Auth mutations (TanStack Query over supabase-js). The AuthProvider's
 * onAuthStateChange subscription updates the store on success - these
 * hooks never write auth state directly.
 */
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { toast } from "sonner";

import { supabase } from "@/lib/supabase";
import { PATHS } from "@/routes/paths";
import type { LoginValues, SignupValues } from "@/features/auth/schemas";

export function useLogin() {
  return useMutation({
    meta: { silent: true }, // form shows the error inline
    mutationFn: async ({ email, password }: LoginValues) => {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw new Error(error.message);
    },
  });
}

export function useSignup() {
  return useMutation({
    meta: { silent: true },
    mutationFn: async ({ email, password }: SignupValues) => {
      const { data, error } = await supabase.auth.signUp({ email, password });
      if (error) throw new Error(error.message);
      return { needsConfirmation: !data.session };
    },
  });
}

export function useLogout() {
  const navigate = useNavigate();
  return useMutation({
    mutationFn: async () => {
      const { error } = await supabase.auth.signOut();
      if (error) throw new Error(error.message);
    },
    onSuccess: () => {
      toast.success("Signed out.");
      void navigate(PATHS.landing);
    },
  });
}
