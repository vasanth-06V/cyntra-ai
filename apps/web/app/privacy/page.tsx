import Link from "next/link";

export const metadata = { title: "Privacy — CyntraAI" };

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <Link href="/" className="text-sm text-muted-foreground hover:underline">
        ← CyntraAI
      </Link>
      <h1 className="mt-4 text-3xl font-semibold">Privacy</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        CyntraAI is a bring-your-own-key app: you connect your own AI provider accounts. This page
        says plainly what is stored, what leaves the app, and how to remove it.
      </p>

      <section className="mt-8 flex flex-col gap-6 text-sm leading-6">
        <div>
          <h2 className="text-lg font-medium">What we store</h2>
          <ul className="mt-2 list-disc pl-5">
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
        </div>

        <div>
          <h2 className="text-lg font-medium">What leaves the app</h2>
          <ul className="mt-2 list-disc pl-5">
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
        </div>

        <div>
          <h2 className="text-lg font-medium">Your controls</h2>
          <ul className="mt-2 list-disc pl-5">
            <li>Delete any saved API key in Settings → API Keys.</li>
            <li>Delete a resume on the Resumes page, and a report with “Delete now” on the report page.</li>
            <li>Browser-only preferences (voice settings, an unsent code draft) live in your browser and can be cleared there.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-medium">Good to know</h2>
          <ul className="mt-2 list-disc pl-5">
            <li>
              Interview scores, code reviews and ATS results are produced by AI models. Treat them as
              guidance for practice, not as a verdict on your ability.
            </li>
            <li>This is a personal project; if you want your data removed, delete it as above or contact the site owner.</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
