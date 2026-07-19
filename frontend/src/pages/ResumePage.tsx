import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";

export default function ResumePage() {
  return (
    <>
      <PageHeader title="Resume Intelligence" description="Upload a resume for structured, evidence-based analysis." />
      <EmptyState title="Coming soon" description="The Resume Intelligence UI arrives in Phase 9B." />
    </>
  );
}
