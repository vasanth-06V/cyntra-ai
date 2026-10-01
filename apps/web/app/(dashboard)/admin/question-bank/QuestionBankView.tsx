import { requireUser } from "@/lib/auth/guards";
import { StubPage } from "@/components/ui/StubPage";

export async function QuestionBankView() {
  // Full Owner/Admin-with-permission gating is wired up alongside the real
  // CRUD in a later phase; for now this just requires being signed in.
  await requireUser();

  return (
    <StubPage
      title="Question Bank"
      description="Manage interview questions and test cases (Owner, or Admin with permission)."
    />
  );
}
