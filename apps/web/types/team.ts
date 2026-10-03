export type TeamRole = "owner" | "admin" | "user";

export type TeamUser = {
  id: string;
  email: string | null;
  full_name: string | null;
  role: TeamRole;
  permissions: string[];
  created_at: string | null;
};
