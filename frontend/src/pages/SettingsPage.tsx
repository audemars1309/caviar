import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" description="Manage your Caviar preferences." />
      <EmptyState title="Coming soon" description="Settings controls arrive in a later phase." />
    </>
  );
}
