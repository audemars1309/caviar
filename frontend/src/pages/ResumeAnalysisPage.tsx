import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router";

import { PageHeader } from "@/components/common/PageHeader";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AnalysisReport } from "@/features/resumes/components/AnalysisReport";
import { useAnalysis } from "@/features/resumes/hooks";
import { PATHS } from "@/routes/paths";
import { formatDateTime } from "@/utils/format";

export default function ResumeAnalysisPage() {
  const { analysisId = "" } = useParams();
  const analysis = useAnalysis(analysisId);

  return (
    <>
      <PageHeader
        title="Resume analysis"
        description={
          analysis.data ? `Generated ${formatDateTime(analysis.data.created_at)}` : undefined
        }
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to={PATHS.resume}>
              <ArrowLeft aria-hidden /> All resumes
            </Link>
          </Button>
        }
      />

      {analysis.isLoading ? (
        <div className="space-y-4" aria-busy>
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : analysis.isError ? (
        <Alert variant="destructive">
          <AlertDescription className="flex items-center justify-between gap-3">
            <span>Could not load this analysis.</span>
            <Button variant="outline" size="sm" onClick={() => void analysis.refetch()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : analysis.data ? (
        analysis.data.status === "FAILED" ? (
          <Alert variant="destructive">
            <AlertDescription>
              {analysis.data.failure_reason ?? "This analysis failed."} Run a new analysis from
              the resume dashboard.
            </AlertDescription>
          </Alert>
        ) : (
          <AnalysisReport analysis={analysis.data} />
        )
      ) : null}
    </>
  );
}
