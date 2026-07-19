import { useEffect, type ReactNode } from "react";

import { applyThemeClass, resolveTheme, useThemeStore } from "@/store/theme";

/** Applies the persisted theme preference to <html>, tracking system
 *  changes while preference is "system". */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const preference = useThemeStore((state) => state.preference);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () =>
      applyThemeClass(document.documentElement, resolveTheme(preference, media.matches));
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [preference]);

  return children;
}
