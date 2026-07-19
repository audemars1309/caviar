import { ArrowLeft, Printer } from "lucide-react";
import { Link, useParams } from "react-router";

import { PageHeader } from "@/components/common/PageHeader";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ReportView } from "@/features/interviews/components/ReportView";
import { useInterviewReport } from "@/features/interviews/hooks";
import { PATHS } from "@/routes/paths";
import { formatDateTime } from "@/utils/format";

/** Report page. Export: the backend does not generate a PDF for
 *  interview reports, so export uses the browser's print-to-PDF via a
 *  print stylesheet - clearly a client print, not a backend document. */
export default function InterviewReportPage() {
  const { sessionId = "" } = useParams();
  const report = useInterviewReport(sessionId);

  return (
    <>
      <div className="print:hidden">
        <PageHeader
          title="Interview report"
          description={report.data ? `Generated ${formatDateTime(report.data.created_at)}` : undefined}
          actions={
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => window.print()}>
                <Printer aria-hidden /> Print / Save as PDF
              </Button>
              <Button asChild variant="ghost" size="sm">
                <Link to={PATHS.interview}>
                  <ArrowLeft aria-hidden /> All interviews
                </Link>
              </Button>
            </div>
          }
        />
      </div>

      {report.isLoading ? (
        <div className="space-y-4" aria-busy>
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : report.isError ? (
        <Alert variant="destructive">
          <AlertDescription className="flex items-center justify-between gap-3">
            <span>
              No report is available for this interview yet. Reports are generated when an
              interview completes.
            </span>
            <Button variant="outline" size="sm" onClick={() => void report.refetch()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : report.data ? (
        <ReportView report={report.data} />
      ) : null}
    </>
  );
}
