import { Link, Outlet } from "react-router";

import { PATHS } from "@/routes/paths";
import { APP_NAME, APP_TAGLINE } from "@/utils/constants";

export function AuthLayout() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 p-6">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-1 text-center">
          <Link to={PATHS.landing} className="text-xl font-semibold tracking-tight">
            {APP_NAME}
          </Link>
          <p className="text-sm text-muted-foreground">{APP_TAGLINE}</p>
        </div>
        <Outlet />
      </div>
    </div>
  );
}
