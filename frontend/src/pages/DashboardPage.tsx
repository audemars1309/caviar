import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";

export default function DashboardPage() {
  return (
    <>
      <PageHeader title="Dashboard" description="Your candidate intelligence at a glance." />
      <EmptyState title="Coming soon" description="Phase 9B and 9C will populate this overview." />
    </>
  );
}
