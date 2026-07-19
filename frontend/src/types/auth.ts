export interface AuthUser {
  id: string;
  email: string | null;
}

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";
