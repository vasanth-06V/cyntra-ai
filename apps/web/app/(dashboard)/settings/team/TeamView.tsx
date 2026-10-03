import { requireRole } from "@/lib/auth/guards";
import { TeamManager } from "./TeamManager";

export async function TeamView() {
  const { user } = await requireRole("owner");

  return <TeamManager currentUserId={user.id} />;
}
