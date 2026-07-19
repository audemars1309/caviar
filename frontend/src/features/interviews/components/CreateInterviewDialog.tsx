/** Interview setup: resume (required, must be EXTRACTED), optional job
 *  context, type (Technical/Behavioral/Mixed), difficulty, duration
 *  5-60 min. All constraints mirror the backend InterviewCreateRequest;
 *  the backend remains authoritative. */
import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import type { Difficulty, InterviewType } from "@/features/interviews/api";
import { useCreateInterview } from "@/features/interviews/hooks";
import { useJobContexts, useResumes } from "@/features/resumes/hooks";
import { getApiErrorMessage } from "@/services/api/errors";

const NO_CONTEXT = "__none__";

export function CreateInterviewDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const resumes = useResumes();
  const jobContexts = useJobContexts();
  const createInterview = useCreateInterview();

  const [resumeId, setResumeId] = useState<string>("");
  const [jobContextId, setJobContextId] = useState<string>(NO_CONTEXT);
  const [interviewType, setInterviewType] = useState<InterviewType>("MIXED");
  const [difficulty, setDifficulty] = useState<Difficulty>("MEDIUM");
  const [duration, setDuration] = useState<string>("20");

  const eligibleResumes = (resumes.data ?? []).filter(
    (resume) => resume.extraction_status === "EXTRACTED",
  );
  const durationNumber = Number(duration);
  const durationValid =
    Number.isInteger(durationNumber) && durationNumber >= 5 && durationNumber <= 60;
  const valid = resumeId !== "" && durationValid;

  const create = () => {
    if (!valid) return;
    createInterview.mutate(
      {
        resume_id: resumeId,
        job_context_id: jobContextId === NO_CONTEXT ? null : jobContextId,
        interview_type: interviewType,
        difficulty,
        duration_minutes: durationNumber,
      },
      {
        onSuccess: (session) => {
          onOpenChange(false);
          void navigate(`/interview/${session.id}`);
        },
        onError: (error) => toast.error(getApiErrorMessage(error)),
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New AI interview</DialogTitle>
          <DialogDescription>
            The AI interviewer adapts its questions to your resume, role, and answers.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="interview-resume">Resume</Label>
            <Select value={resumeId} onValueChange={setResumeId}>
              <SelectTrigger id="interview-resume" aria-label="Resume">
                <SelectValue placeholder="Choose an analyzed resume" />
              </SelectTrigger>
              <SelectContent>
                {eligibleResumes.map((resume) => (
                  <SelectItem key={resume.id} value={resume.id}>
                    {resume.original_filename}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {resumes.isSuccess && eligibleResumes.length === 0 ? (
              <p className="text-xs text-destructive">
                Upload a resume first - interviews are grounded in your resume.
              </p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="interview-job-context">Target role (optional)</Label>
            <Select value={jobContextId} onValueChange={setJobContextId}>
              <SelectTrigger id="interview-job-context" aria-label="Target role">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_CONTEXT}>No specific role</SelectItem>
                {(jobContexts.data ?? []).map((context) => (
                  <SelectItem key={context.id} value={context.id}>
                    {context.target_role}
                    {context.company_name ? ` — ${context.company_name}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="interview-type">Type</Label>
              <Select
                value={interviewType}
                onValueChange={(value) => setInterviewType(value as InterviewType)}
              >
                <SelectTrigger id="interview-type" aria-label="Interview type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="MIXED">Mixed</SelectItem>
                  <SelectItem value="TECHNICAL">Technical</SelectItem>
                  <SelectItem value="BEHAVIORAL">Behavioral</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="interview-difficulty">Difficulty</Label>
              <Select
                value={difficulty}
                onValueChange={(value) => setDifficulty(value as Difficulty)}
              >
                <SelectTrigger id="interview-difficulty" aria-label="Difficulty">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="EASY">Easy</SelectItem>
                  <SelectItem value="MEDIUM">Medium</SelectItem>
                  <SelectItem value="HARD">Hard</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="interview-duration">Duration (min)</Label>
              <Input
                id="interview-duration"
                type="number"
                min={5}
                max={60}
                value={duration}
                onChange={(event) => setDuration(event.target.value)}
                aria-invalid={!durationValid}
              />
              {!durationValid ? (
                <p className="text-xs text-destructive">Between 5 and 60 minutes.</p>
              ) : null}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={create} disabled={!valid || createInterview.isPending}>
            {createInterview.isPending ? <Spinner className="text-primary-foreground" /> : null}
            Create interview
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
