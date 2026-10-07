import { redirect } from "next/navigation";

// Resumes now live under Settings; this keeps old links and bookmarks working.
export default function ResumesRedirect() {
  redirect("/settings/resumes");
}
