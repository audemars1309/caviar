import { Badge } from "@/components/ui/badge";
import { STATUS_LABELS } from "@/features/interviews/api";

const VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  COMPLETED: "default",
  RUNNING: "secondary",
  PAUSED: "secondary",
  READY: "outline",
  PENDING: "outline",
  FAILED: "destructive",
  CANCELLED: "outline",
};

export function InterviewStatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={VARIANTS[status] ?? "outline"}>{STATUS_LABELS[status] ?? status}</Badge>
  );
}
