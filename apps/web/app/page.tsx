import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Landing } from "@/components/landing/Landing";
import { createClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: { absolute: "CyntraAI | Mock interviews, resume scoring and AI chat" },
  description:
    "Rehearse timed mock interviews built from your resume, score your resume like an applicant tracking system would, and chat with Gemini, Claude or Groq. Runs on your own AI key.",
  openGraph: {
    title: "CyntraAI | Mock interviews, resume scoring and AI chat",
    description: "Practice interviews and fix your resume on your own AI key. No subscription.",
    type: "website",
  },
};

export default async function RootPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Signed-in visitors skip the pitch and land in the app.
  if (user) redirect("/dashboard");

  return <Landing />;
}
