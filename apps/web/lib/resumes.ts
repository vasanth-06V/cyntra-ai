import type { Resume } from "@/types/resumes";

/** Each account keeps at most this many resumes. Enforced in app/api/resumes/route.ts too. */
export const MAX_RESUMES = 3;
export const MAX_RESUME_BYTES = 500 * 1024;
export const RESUME_EXTENSIONS = ["pdf", "docx"] as const;

export const MAX_RESUME_NAME_LENGTH = 80;

/** The owner's chosen name, or the file name without the storage folder. */
export function resumeName(resume: Pick<Resume, "file_key" | "display_name">): string {
  return resume.display_name?.trim() || (resume.file_key.split("/").pop() ?? resume.file_key);
}

/** First problem with a proposed resume name (empty is allowed: it clears the name). */
export function validateResumeName(value: string): string | null {
  return value.trim().length > MAX_RESUME_NAME_LENGTH
    ? `Keep the name to ${MAX_RESUME_NAME_LENGTH} characters or fewer.`
    : null;
}

/** First problem with a file chosen for upload, or null when it looks fine. */
export function validateResumeFile(file: { name: string; size: number }): string | null {
  const ext = file.name.split(".").pop()?.toLowerCase();
  if (!ext || !(RESUME_EXTENSIONS as readonly string[]).includes(ext)) {
    return "Only PDF and DOCX files are supported.";
  }
  if (file.size === 0) return "That file is empty.";
  if (file.size > MAX_RESUME_BYTES) return "That file is too large (max 500KB).";
  return null;
}

/**
 * Loads the signed-in user's resumes from the Next route handler. Unlike a bare
 * `fetch().then(r => r.json())`, a failure (401, 500, HTML error page) becomes
 * a thrown Error with a readable message instead of a non-array "result".
 */
export async function fetchResumes(): Promise<Resume[]> {
  let res: Response;
  try {
    res = await fetch("/api/resumes", { cache: "no-store" });
  } catch {
    throw new Error("Could not reach the server. Check your connection and try again.");
  }
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const message = (body as { error?: string } | null)?.error;
    throw new Error(message || "Could not load resumes.");
  }
  if (!Array.isArray(body)) throw new Error("Could not load resumes.");
  return body as Resume[];
}
