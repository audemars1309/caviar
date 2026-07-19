import { Badge } from "@/components/ui/badge";

const STATUS_STYLES: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  EXTRACTED: { label: "Ready", variant: "default" },
  PENDING: { label: "Processing", variant: "secondary" },
  FAILED: { label: "Extraction failed", variant: "destructive" },
};

export function ResumeStatusBadge({ status }: { status: string }) {
  const entry = STATUS_STYLES[status] ?? { label: status, variant: "outline" as const };
  return <Badge variant={entry.variant}>{entry.label}</Badge>;
}
