/** Interview Dashboard: history with filter/search, readiness trend
 *  from backend reports, and the setup flow. "Upcoming interviews" have
 *  no backend concept (no scheduling); created-but-unstarted sessions
 *  fill that role and are shown as "Ready to start". */
import { Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { STATUS_LABELS } from "@/features/interviews/api";
import { CreateInterviewDialog } from "@/features/interviews/components/CreateInterviewDialog";
import { InterviewCard } from "@/features/interviews/components/InterviewCard";
import { ReadinessTrend } from "@/features/interviews/components/ReadinessTrend";
import { useInterviews, useReadinessTrend } from "@/features/interviews/hooks";

const ALL = "__all__";

export default function InterviewPage() {
  const interviews = useInterviews();
  const trend = useReadinessTrend(interviews.data);
  const [createOpen, setCreateOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>(ALL);
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return (interviews.data ?? []).filter((session) => {
      if (statusFilter !== ALL && session.status !== statusFilter) return false;
      if (query) {
        const haystack =
          `${session.target_role_snapshot ?? ""} ${session.interview_type} ${session.difficulty}`.toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
  }, [interviews.data, statusFilter, search]);

  return (
    <>
      <PageHeader
        title="AI Interviews"
        description="Adaptive mock interviews grounded in your resume, with evidence-based reports."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus aria-hidden /> New interview
          </Button>
        }
      />

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Readiness trend</CardTitle>
          </CardHeader>
          <CardContent>
            {trend.isLoading ? (
              <Skeleton className="h-32 w-full max-w-xl" />
            ) : (
              <ReadinessTrend points={trend.points} />
            )}
          </CardContent>
        </Card>

        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-48 flex-1 space-y-1.5">
            <Label htmlFor="interview-search">Search</Label>
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Input
                id="interview-search"
                className="pl-8"
                placeholder="Role, type, difficulty…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="interview-status-filter">Status</Label>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger id="interview-status-filter" className="w-44" aria-label="Filter by status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All statuses</SelectItem>
                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {interviews.isLoading ? (
          <div className="space-y-3" aria-busy>
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : interviews.isError ? (
          <Alert variant="destructive">
            <AlertDescription className="flex items-center justify-between gap-3">
              <span>Could not load your interviews.</span>
              <Button variant="outline" size="sm" onClick={() => void interviews.refetch()}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        ) : (interviews.data ?? []).length === 0 ? (
          <EmptyState
            title="No interviews yet"
            description="Create your first AI interview - it adapts to your resume and target role."
            action={
              <Button onClick={() => setCreateOpen(true)}>
                <Plus aria-hidden /> New interview
              </Button>
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState title="No matches" description="Adjust the search or status filter." />
        ) : (
          <ul className="space-y-3">
            {filtered.map((session) => (
              <li key={session.id}>
                <InterviewCard session={session} />
              </li>
            ))}
          </ul>
        )}
      </div>

      <CreateInterviewDialog open={createOpen} onOpenChange={setCreateOpen} />
    </>
  );
}
