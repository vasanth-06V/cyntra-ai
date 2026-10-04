import { requirePermission } from "@/lib/auth/guards";
import { QuestionBankView } from "./QuestionBankView";

export const metadata = { title: "Question bank" };

export default async function QuestionBankPage() {
  await requirePermission("manage_question_bank");
  return <QuestionBankView />;
}
