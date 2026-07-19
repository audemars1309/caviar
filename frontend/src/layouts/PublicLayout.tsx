import { Link, Outlet } from "react-router";

import { Button } from "@/components/ui/button";
import { Footer } from "@/layouts/components/Footer";
import { ThemeToggle } from "@/layouts/components/ThemeToggle";
import { PATHS } from "@/routes/paths";
import { APP_NAME } from "@/utils/constants";

export function PublicLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex h-14 items-center justify-between border-b px-6">
        <Link to={PATHS.landing} className="font-semibold tracking-tight">
          {APP_NAME}
        </Link>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button asChild variant="ghost" size="sm">
            <Link to={PATHS.login}>Sign in</Link>
          </Button>
          <Button asChild size="sm">
            <Link to={PATHS.signup}>Get started</Link>
          </Button>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
