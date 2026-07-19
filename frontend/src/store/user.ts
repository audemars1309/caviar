/**
 * User preference/profile CLIENT state (display name shown in the shell,
 * onboarding flags). The authoritative profile lives on the server and
 * is fetched via TanStack Query; this store only mirrors what the shell
 * needs synchronously between navigations.
 */
import { create } from "zustand";

interface UserState {
  displayName: string | null;
  setDisplayName: (name: string | null) => void;
  reset: () => void;
}

export const useUserStore = create<UserState>((set) => ({
  displayName: null,
  setDisplayName: (displayName) => set({ displayName }),
  reset: () => set({ displayName: null }),
}));
