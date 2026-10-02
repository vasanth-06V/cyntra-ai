import { requirePermission } from "@/lib/auth/guards";
import { QuestionBankView } from "./QuestionBankView";

export default async function QuestionBankPage() {
  await requirePermission("manage_question_bank");
  return <QuestionBankView />;
}
