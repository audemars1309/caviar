import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";

export default function ProfilePage() {
  return (
    <>
      <PageHeader title="Profile" description="Your account and candidate profile." />
      <EmptyState title="Coming soon" description="Profile management arrives in a later phase." />
    </>
  );
}
