/** Permission keys an Owner can grant to an Admin. The single place they are listed. */
export const TEAM_PERMISSIONS = [
  {
    key: "manage_question_bank",
    label: "Manage the question bank",
    hint: "Add, edit and delete interview questions.",
  },
] as const;

export type TeamPermissionKey = (typeof TEAM_PERMISSIONS)[number]["key"];

export const ROLE_LABELS = { owner: "Owner", admin: "Admin", user: "User" } as const;
