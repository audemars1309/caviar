import { Toaster as SonnerToaster } from "sonner";

import { useTheme } from "@/hooks/useTheme";

/** App-wide toast outlet (sonner), following the active theme. */
function Toaster() {
  const { resolved } = useTheme();
  return <SonnerToaster theme={resolved} position="top-right" richColors closeButton />;
}

export { Toaster };
