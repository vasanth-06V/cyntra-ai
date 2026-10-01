import { requireRole } from "@/lib/auth/guards";
import { StubPage } from "@/components/ui/StubPage";

export async function TeamView() {
  await requireRole("owner");

  return (
    <StubPage
      title="Team"
      description="Promote users to Admin and grant custom permissions (Owner only)."
    />
  );
}
