import { useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Resume } from "@/features/resumes/api";
import { AnalyzeDialog } from "@/features/resumes/components/AnalyzeDialog";
import { ResumeCard } from "@/features/resumes/components/ResumeCard";
import { ResumeUploadDropzone } from "@/features/resumes/components/ResumeUploadDropzone";
import { useResumes, useResumeUpload } from "@/features/resumes/hooks";

export default function ResumePage() {
  const resumes = useResumes();
  const upload = useResumeUpload(resumes.data ?? []);
  const [analyzing, setAnalyzing] = useState<Resume | null>(null);

  return (
    <>
      <PageHeader
        title="Resume Intelligence"
        description="Upload resumes and get structured, evidence-based analysis."
      />

      <div className="space-y-6">
        <ResumeUploadDropzone
          state={upload.state}
          onFile={(file) => void upload.start(file)}
          onCancel={upload.cancel}
          onRetry={upload.retry}
        />

        {resumes.isLoading ? (
          <div className="space-y-3" aria-busy>
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : resumes.isError ? (
          <Alert variant="destructive">
            <AlertDescription className="flex items-center justify-between gap-3">
              <span>Could not load your resumes.</span>
              <Button variant="outline" size="sm" onClick={() => void resumes.refetch()}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        ) : (resumes.data ?? []).length === 0 ? (
          <EmptyState
            title="No resumes yet"
            description="Upload a PDF resume above to run your first analysis."
          />
        ) : (
          <ul className="space-y-3">
            {(resumes.data ?? []).map((resume) => (
              <li key={resume.id}>
                <ResumeCard resume={resume} onAnalyze={setAnalyzing} />
              </li>
            ))}
          </ul>
        )}
      </div>

      <AnalyzeDialog
        resume={analyzing}
        onOpenChange={(open) => {
          if (!open) setAnalyzing(null);
        }}
      />
    </>
  );
}
