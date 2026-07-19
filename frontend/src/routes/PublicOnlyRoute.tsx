import { Navigate, Outlet } from "react-router";

import { LoadingScreen } from "@/components/common/LoadingScreen";
import { useAuth } from "@/hooks/useAuth";
import { PATHS } from "@/routes/paths";

/** Login/signup are for signed-out users; signed-in users go to the app. */
export function PublicOnlyRoute() {
  const { status } = useAuth();
  if (status === "loading") return <LoadingScreen label="Checking your session" />;
  if (status === "authenticated") return <Navigate to={PATHS.dashboard} replace />;
  return <Outlet />;
}
