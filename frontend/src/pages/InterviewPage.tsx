import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";

export default function InterviewPage() {
  return (
    <>
      <PageHeader title="AI Interview" description="Practice adaptive interviews with evidence-based evaluation." />
      <EmptyState title="Coming soon" description="The Interview Room arrives in Phase 9C." />
    </>
  );
}
