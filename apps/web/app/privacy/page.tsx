import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { Logo } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

export const metadata = { title: "Privacy — CyntraAI" };

export default function PrivacyPage() {
  return (
    <div className="brand-wash min-h-screen">
    <main className="mx-auto max-w-2xl px-4 py-8 sm:px-6 sm:py-12">
      <div className="flex items-center justify-between">
        <Link href="/" className="rounded-lg text-sm text-muted-foreground transition-colors hover:text-foreground">
          <span className="sr-only">CyntraAI home</span>
          <span aria-hidden="true" className="flex items-center gap-2">
            ← <Logo size={24} />
          </span>
        </Link>
        <ThemeToggle />
      </div>
      <h1 className="mt-10 text-4xl font-semibold tracking-[-0.035em]">Privacy</h1>
      <p className="mt-3 text-[15px] leading-7 text-muted-foreground">
        CyntraAI is a bring-your-own-key app: you connect your own AI provider accounts. This page
        says plainly what is stored, what leaves the app, and how to remove it.
      </p>

      <section className="stagger mt-8 flex flex-col gap-4 text-sm leading-6">
        <Card className="p-5 sm:p-6">
          <h2 className="text-lg font-semibold tracking-tight">What we store</h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 marker:text-primary">
            <li>Your Google account name and email (to sign you in).</li>
            <li>
              Your AI provider API keys, <strong>encrypted</strong> on our server. They are never shown
              again and never sent to your browser.
            </li>
            <li>Resumes you upload (the file and the text extracted from it) until you delete them.</li>
            <li>Your chat conversations and interview transcripts, and the code you submit in a coding round.</li>
            <li>
              Interview reports, which are deleted automatically <strong>7 days</strong> after they are made
              (or earlier if you delete them).
            </li>
            <li>Daily usage counts (requests and tokens) so you can see your own consumption.</li>
          </ul>
        </Card>

        <Card className="p-5 sm:p-6">
          <h2 className="text-lg font-semibold tracking-tight">What leaves the app</h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 marker:text-primary">
            <li>
              Your prompts, answers, resume excerpts, job descriptions and submitted code are sent to the
              AI provider whose key you chose (Gemini, Groq or Claude), using <strong>your</strong> key and
              under <strong>their</strong> terms and quotas.
            </li>
            <li>
              If you turn on voice, your browser&apos;s speech recognition turns your speech into text. In
              Chrome and Edge that processing is done by Google&apos;s speech service. Voice is optional;
              typing always works. The interviewer&apos;s spoken voice uses your browser&apos;s built-in voices (some browsers&apos; voices are provided online).
            </li>
            <li>We do not sell your data and we do not use it to train models.</li>
          </ul>
        </Card>

        <Card className="p-5 sm:p-6">
          <h2 className="text-lg font-semibold tracking-tight">Your controls</h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 marker:text-primary">
            <li>Delete any saved API key in Settings → API Keys.</li>
            <li>Delete a resume on the Resumes page, and a report with “Delete now” on the report page.</li>
            <li>Browser-only preferences (voice settings, an unsent code draft) live in your browser and can be cleared there.</li>
          </ul>
        </Card>

        <Card className="p-5 sm:p-6">
          <h2 className="text-lg font-semibold tracking-tight">Good to know</h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 marker:text-primary">
            <li>
              Interview scores, code reviews and ATS results are produced by AI models. Treat them as
              guidance for practice, not as a verdict on your ability.
            </li>
            <li>This is a personal project; if you want your data removed, delete it as above or contact the site owner.</li>
          </ul>
        </Card>
      </section>
    </main>
    </div>
  );
}
