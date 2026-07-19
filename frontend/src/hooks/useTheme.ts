import { resolveTheme, useThemeStore } from "@/store/theme";

export function useTheme() {
  const preference = useThemeStore((state) => state.preference);
  const setPreference = useThemeStore((state) => state.setPreference);
  const systemPrefersDark =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  return { preference, setPreference, resolved: resolveTheme(preference, systemPrefersDark) };
}
