import { FileText, Home, MessageSquare, PenLine, Settings, User } from "lucide-react";
import { NavLink } from "react-router";

import { cn } from "@/lib/utils";
import { PATHS } from "@/routes/paths";
import { useUiStore } from "@/store/ui";

const NAV_ITEMS = [
  { to: PATHS.dashboard, label: "Dashboard", icon: Home },
  { to: PATHS.resume, label: "Resume Intelligence", icon: FileText },
  { to: PATHS.resumeBuilder, label: "Resume Builder", icon: PenLine },
  { to: PATHS.interview, label: "AI Interview", icon: MessageSquare },
  { to: PATHS.profile, label: "Profile", icon: User },
  { to: PATHS.settings, label: "Settings", icon: Settings },
] as const;

export function Sidebar() {
  const sidebarOpen = useUiStore((state) => state.sidebarOpen);
  const setSidebarOpen = useUiStore((state) => state.setSidebarOpen);
  return (
    <nav
      aria-label="Primary"
      className={cn(
        "fixed inset-y-0 left-0 z-30 w-60 border-r bg-background pt-14 transition-transform md:static md:translate-x-0 md:pt-0",
        sidebarOpen ? "translate-x-0" : "-translate-x-full",
      )}
    >
      <ul className="space-y-1 p-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                )
              }
            >
              <Icon className="size-4" aria-hidden />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
