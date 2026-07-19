/** Backend-owned stage indicator: highlights the current stage in the
 *  fixed interview state machine plus the question budget. */
import { INTERVIEW_STAGES } from "@/features/interviews/api";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

const STAGE_SHORT: Record<string, string> = {
  INTRODUCTION: "Intro",
  CANDIDATE_BACKGROUND: "Background",
  RESUME_DISCUSSION: "Resume",
  PROJECT_DEEP_DIVE: "Projects",
  ROLE_SPECIFIC: "Role",
  BEHAVIORAL: "Behavioral",
  ADAPTIVE_PROBING: "Probing",
  CLOSING: "Closing",
  COMPLETED: "Done",
};

export function StageProgress({
  currentStage,
  questionsUsed,
  questionBudget,
}: {
  currentStage: string;
  questionsUsed: number;
  questionBudget: number;
}) {
  const percent = questionBudget > 0 ? (questionsUsed / questionBudget) * 100 : 0;
  return (
    <div className="space-y-2">
      <ol className="flex flex-wrap gap-1.5" aria-label="Interview stages">
        {INTERVIEW_STAGES.map((stage) => (
          <li
            key={stage}
            aria-current={stage === currentStage ? "step" : undefined}
            className={cn(
              "rounded-full border px-2 py-0.5 text-[0.7rem]",
              stage === currentStage
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border text-muted-foreground",
            )}
          >
            {STAGE_SHORT[stage] ?? stage}
          </li>
        ))}
      </ol>
      <div className="flex items-center gap-3">
        <Progress value={percent} label="Question budget used" className="max-w-64" />
        <span className="text-xs tabular-nums text-muted-foreground">
          {questionsUsed}/{questionBudget} questions
        </span>
      </div>
    </div>
  );
}
