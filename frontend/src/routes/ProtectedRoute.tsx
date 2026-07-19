import { Navigate, Outlet, useLocation } from "react-router";

import { LoadingScreen } from "@/components/common/LoadingScreen";
import { useAuth } from "@/hooks/useAuth";
import { PATHS } from "@/routes/paths";

/**
 * Route guard for authenticated areas. While the session is being
 * restored we hold on a loading screen (never flash the login page);
 * unauthenticated users are redirected to login with the intended
 * destination preserved for post-login redirect.
 */
export function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <LoadingScreen label="Checking your session" />;
  if (status === "unauthenticated") {
    return <Navigate to={PATHS.login} replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
