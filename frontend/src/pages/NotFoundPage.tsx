import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { PATHS } from "@/routes/paths";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <p className="text-sm font-medium text-muted-foreground">404</p>
      <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        The page you are looking for does not exist or has moved.
      </p>
      <Button asChild>
        <Link to={PATHS.landing}>Back to home</Link>
      </Button>
    </div>
  );
}
