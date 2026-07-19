import { Menu } from "lucide-react";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/layouts/components/ThemeToggle";
import { UserMenu } from "@/layouts/components/UserMenu";
import { PATHS } from "@/routes/paths";
import { useUiStore } from "@/store/ui";
import { APP_NAME } from "@/utils/constants";

export function Header() {
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        aria-label="Toggle navigation"
        onClick={toggleSidebar}
      >
        <Menu aria-hidden />
      </Button>
      <Link to={PATHS.dashboard} className="font-semibold tracking-tight">
        {APP_NAME}
      </Link>
      <div className="ml-auto flex items-center gap-2">
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
