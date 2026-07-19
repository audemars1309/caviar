import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";

export default function ResumeBuilderPage() {
  return (
    <>
      <PageHeader title="Resume Builder" description="Build structured, ATS-safe resumes with AI assistance." />
      <EmptyState title="Coming soon" description="The Resume Builder UI arrives in Phase 9B." />
    </>
  );
}
