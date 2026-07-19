import { FileBarChart, Play, XCircle } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { InterviewSession } from "@/features/interviews/api";
import { InterviewStatusBadge } from "@/features/interviews/components/InterviewStatusBadge";
import { useCancelInterview } from "@/features/interviews/hooks";
import { formatDateTime } from "@/utils/format";

const STAGE_TEXT: Record<string, string> = {
  INTRODUCTION: "Introduction",
  CANDIDATE_BACKGROUND: "Background",
  RESUME_DISCUSSION: "Resume discussion",
  PROJECT_DEEP_DIVE: "Project deep dive",
  ROLE_SPECIFIC: "Role-specific",
  BEHAVIORAL: "Behavioral",
  ADAPTIVE_PROBING: "Adaptive probing",
  CLOSING: "Closing",
  COMPLETED: "Completed",
};

export function InterviewCard({ session }: { session: InterviewSession }) {
  const navigate = useNavigate();
  const cancelInterview = useCancelInterview();
  const [confirmCancel, setConfirmCancel] = useState(false);

  const openable = ["PENDING", "READY", "RUNNING", "PAUSED"].includes(session.status);
  const cancellable = ["PENDING", "READY", "RUNNING", "PAUSED"].includes(session.status);

  return (
    <Card>
      <CardContent className="flex flex-wrap items-center gap-4 p-4">
        <div className="min-w-0 flex-1 space-y-1">
          <p className="truncate font-medium">
            {session.target_role_snapshot ?? "General interview"}{" "}
            <span className="font-normal text-muted-foreground">
              · {session.interview_type} · {session.difficulty}
            </span>
          </p>
          <p className="text-xs text-muted-foreground">
            {formatDateTime(session.created_at)} · Stage:{" "}
            {STAGE_TEXT[session.current_stage] ?? session.current_stage} · Questions{" "}
            {session.question_budget_used}/{session.question_budget}
          </p>
          {session.status === "FAILED" && session.failure_reason ? (
            <p className="text-xs text-destructive">{session.failure_reason}</p>
          ) : null}
        </div>
        <InterviewStatusBadge status={session.status} />
        <div className="flex items-center gap-2">
          {openable ? (
            <Button size="sm" onClick={() => void navigate(`/interview/${session.id}`)}>
              <Play aria-hidden />
              {session.status === "RUNNING" || session.status === "PAUSED"
                ? "Continue"
                : "Start"}
            </Button>
          ) : null}
          {session.status === "COMPLETED" ? (
            <Button asChild size="sm" variant="outline">
              <Link to={`/interview/${session.id}/report`}>
                <FileBarChart aria-hidden /> Report
              </Link>
            </Button>
          ) : null}
          {cancellable ? (
            <Button
              size="icon"
              variant="ghost"
              aria-label="End this interview"
              onClick={() => setConfirmCancel(true)}
            >
              <XCircle aria-hidden />
            </Button>
          ) : (
            <Button
              size="icon"
              variant="ghost"
              disabled
              aria-label="Delete interview (not supported by the backend)"
              title="Deleting interviews is not supported by the backend yet"
            >
              <XCircle aria-hidden />
            </Button>
          )}
        </div>
      </CardContent>

      <ConfirmDialog
        open={confirmCancel}
        onOpenChange={setConfirmCancel}
        title="End this interview?"
        description="The session will be cancelled. Cancelled interviews cannot be resumed."
        confirmLabel="End interview"
        destructive
        pending={cancelInterview.isPending}
        onConfirm={() =>
          cancelInterview.mutate(session.id, { onSuccess: () => setConfirmCancel(false) })
        }
      />
    </Card>
  );
}
