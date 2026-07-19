import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { Textarea } from "@/components/ui/textarea";
import type { Resume } from "@/features/resumes/api";
import {
  useCreateAnalysis,
  useCreateJobContext,
  useJobContexts,
} from "@/features/resumes/hooks";
import { getApiErrorMessage } from "@/services/api/errors";

const NO_CONTEXT = "__none__";
const NEW_CONTEXT = "__new__";

/** Run-analysis dialog: optional job context for role relevance (pick an
 *  existing one, none, or create one inline). */
export function AnalyzeDialog({
  resume,
  onOpenChange,
}: {
  resume: Resume | null;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const jobContexts = useJobContexts();
  const createJobContext = useCreateJobContext();
  const createAnalysis = useCreateAnalysis();
  const [selection, setSelection] = useState<string>(NO_CONTEXT);
  const [targetRole, setTargetRole] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [jobDescription, setJobDescription] = useState("");

  const pending = createAnalysis.isPending || createJobContext.isPending;

  const run = async () => {
    if (!resume) return;
    try {
      let jobContextId: string | null = selection === NO_CONTEXT ? null : selection;
      if (selection === NEW_CONTEXT) {
        if (targetRole.trim().length < 2) {
          toast.error("Enter a target role (at least 2 characters).");
          return;
        }
        const created = await createJobContext.mutateAsync({
          target_role: targetRole.trim(),
          ...(companyName.trim() ? { company_name: companyName.trim() } : {}),
          ...(jobDescription.trim() ? { job_description: jobDescription.trim() } : {}),
        });
        jobContextId = created.id;
      }
      const analysis = await createAnalysis.mutateAsync({
        resumeId: resume.id,
        jobContextId,
      });
      onOpenChange(false);
      if (analysis.status === "FAILED") {
        toast.error(analysis.failure_reason ?? "Analysis failed. You can retry.");
      } else {
        void navigate(`/resume/analyses/${analysis.id}`);
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    }
  };

  return (
    <Dialog open={resume !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Analyze resume</DialogTitle>
          <DialogDescription>
            Optionally attach a target role so the analysis includes role relevance.
            Scores are computed by the Caviar backend.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="job-context-select">Job context</Label>
            <Select value={selection} onValueChange={setSelection}>
              <SelectTrigger id="job-context-select" aria-label="Job context">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_CONTEXT}>No target role (general analysis)</SelectItem>
                {(jobContexts.data ?? []).map((context) => (
                  <SelectItem key={context.id} value={context.id}>
                    {context.target_role}
                    {context.company_name ? ` — ${context.company_name}` : ""}
                  </SelectItem>
                ))}
                <SelectItem value={NEW_CONTEXT}>+ New job context…</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {selection === NEW_CONTEXT ? (
            <div className="space-y-3 rounded-md border p-3">
              <div className="space-y-2">
                <Label htmlFor="target-role">Target role</Label>
                <Input
                  id="target-role"
                  value={targetRole}
                  onChange={(event) => setTargetRole(event.target.value)}
                  placeholder="e.g. Backend Engineer"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="company-name">Company (optional)</Label>
                <Input
                  id="company-name"
                  value={companyName}
                  onChange={(event) => setCompanyName(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="job-description">Job description (optional)</Label>
                <Textarea
                  id="job-description"
                  rows={4}
                  value={jobDescription}
                  onChange={(event) => setJobDescription(event.target.value)}
                  placeholder="Paste the job description for deeper relevance analysis"
                />
              </div>
            </div>
          ) : null}

          {createAnalysis.isPending ? (
            <Alert>
              <AlertDescription className="flex items-center gap-2">
                <Spinner /> Running AI analysis — this can take up to a minute.
              </AlertDescription>
            </Alert>
          ) : null}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
            Cancel
          </Button>
          <Button onClick={() => void run()} disabled={pending}>
            {pending ? <Spinner className="text-primary-foreground" /> : null}
            Run analysis
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
