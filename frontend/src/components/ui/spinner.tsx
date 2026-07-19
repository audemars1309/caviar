import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

function Spinner({ className, label = "Loading" }: { className?: string; label?: string }) {
  return (
    <span role="status" aria-label={label} className="inline-flex">
      <Loader2 aria-hidden className={cn("size-5 animate-spin text-muted-foreground", className)} />
    </span>
  );
}

export { Spinner };
