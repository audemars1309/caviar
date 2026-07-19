import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useLogout } from "@/features/auth/hooks";
import { useAuth } from "@/hooks/useAuth";

export function UserMenu() {
  const { user } = useAuth();
  const logout = useLogout();
  return (
    <div className="flex items-center gap-3">
      <span className="hidden max-w-48 truncate text-sm text-muted-foreground sm:inline">
        {user?.email ?? "Signed in"}
      </span>
      <Button
        variant="outline"
        size="sm"
        onClick={() => logout.mutate()}
        disabled={logout.isPending}
      >
        <LogOut aria-hidden />
        Sign out
      </Button>
    </div>
  );
}
