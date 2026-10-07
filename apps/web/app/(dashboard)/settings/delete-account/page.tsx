import { requireUser } from "@/lib/auth/guards";
import { DeleteAccountForm } from "./DeleteAccountForm";

export const metadata = { title: "Delete account" };

export default async function DeleteAccountPage() {
  const { role } = await requireUser();
  return <DeleteAccountForm isOwner={role === "owner"} />;
}
