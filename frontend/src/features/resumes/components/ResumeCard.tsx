import { BarChart3, Download, MoreVertical, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { resumesApi, type Resume } from "@/features/resumes/api";
import { useDeleteResume, useResumeAnalyses, useRetryExtraction } from "@/features/resumes/hooks";
import { ResumeStatusBadge } from "@/features/resumes/components/ResumeStatusBadge";
import { getApiErrorMessage } from "@/services/api/errors";
import { formatDateTime, formatFileSize } from "@/utils/format";

export function ResumeCard({
  resume,
  onAnalyze,
}: {
  resume: Resume;
  onAnalyze: (resume: Resume) => void;
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const deleteResume = useDeleteResume();
  const retryExtraction = useRetryExtraction();
  const analyses = useResumeAnalyses(resume.id);
  const latest = analyses.data?.[0];

  const handleDownload = async () => {
    try {
      const { url } = await resumesApi.download(resume.id);
      window.open(url, "_blank", "noopener");
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    }
  };

  return (
    <Card>
      <CardContent className="flex flex-wrap items-center gap-4 p-4">
        <div className="min-w-0 flex-1 space-y-1">
          <p className="truncate font-medium">{resume.original_filename}</p>
          <p className="text-xs text-muted-foreground">
            {formatFileSize(resume.file_size_bytes)} · Modified {formatDateTime(resume.updated_at)}
          </p>
          {resume.extraction_status === "FAILED" && resume.extraction_failure_reason ? (
            <p className="text-xs text-destructive">{resume.extraction_failure_reason}</p>
          ) : null}
        </div>

        <div className="flex items-center gap-3">
          <ResumeStatusBadge status={resume.extraction_status} />
          {analyses.isLoading ? (
            <Skeleton className="h-5 w-24" />
          ) : latest ? (
            latest.status === "COMPLETED" && latest.overall_score !== null ? (
              <Link
                to={`/resume/analyses/${latest.id}`}
                className="text-sm font-medium underline-offset-4 hover:underline"
              >
                Latest score: {latest.overall_score}/100
              </Link>
            ) : (
              <span className="text-sm text-muted-foreground">
                {latest.status === "FAILED" ? "Last analysis failed" : "Analysis pending"}
              </span>
            )
          ) : (
            <span className="text-sm text-muted-foreground">Not analyzed</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => onAnalyze(resume)}
            disabled={resume.extraction_status !== "EXTRACTED"}
          >
            <BarChart3 aria-hidden /> Analyze
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label={`Actions for ${resume.original_filename}`}>
                <MoreVertical aria-hidden />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => void handleDownload()}>
                <Download aria-hidden /> Download original
              </DropdownMenuItem>
              {resume.extraction_status === "FAILED" ? (
                <DropdownMenuItem
                  disabled={retryExtraction.isPending}
                  onSelect={() => retryExtraction.mutate(resume.id)}
                >
                  <RotateCcw aria-hidden /> Retry extraction
                </DropdownMenuItem>
              ) : null}
              <DropdownMenuSeparator className="my-1 h-px bg-border" />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onSelect={() => setConfirmDelete(true)}
              >
                <Trash2 aria-hidden /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardContent>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete this resume?"
        description={`"${resume.original_filename}" and its analyses will be permanently removed.`}
        confirmLabel="Delete"
        destructive
        pending={deleteResume.isPending}
        onConfirm={() =>
          deleteResume.mutate(resume.id, { onSuccess: () => setConfirmDelete(false) })
        }
      />
    </Card>
  );
}
