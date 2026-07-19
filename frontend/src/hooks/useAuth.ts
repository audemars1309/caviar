import { useAuthStore } from "@/store/auth";

/** Read-only auth facade for components. */
export function useAuth() {
  const status = useAuthStore((state) => state.status);
  const user = useAuthStore((state) => state.user);
  return { status, user, isAuthenticated: status === "authenticated" };
}
