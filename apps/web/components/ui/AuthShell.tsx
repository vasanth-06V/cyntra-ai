import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";
import { ChatIcon, GaugeIcon, MicIcon, ShieldIcon } from "./icons";

const HIGHLIGHTS = [
  { icon: MicIcon, title: "Mock interviews that talk back", text: "A timed, voice-ready interview built from your resume and the job description." },
  { icon: GaugeIcon, title: "See your resume the way an ATS does", text: "Keyword, semantic and formatting scores with concrete fixes." },
  { icon: ChatIcon, title: "Bring your own AI key", text: "Gemini, Groq or Claude. Your keys stay encrypted and under your control." },
];

/**
 * Frame for the signed-out screens: brand panel on large screens, a centred
 * card everywhere. Pure presentation; the form goes in `children`.
 */
export function AuthShell({
  children,
  showcase = false,
  footer = true,
  wide = false,
}: {
  children: ReactNode;
  /** Large-screen marketing panel beside the form. */
  showcase?: boolean;
  footer?: boolean;
  /** Wider column for multi-field flows such as onboarding. */
  wide?: boolean;
}) {
  return (
    <div className="brand-wash relative flex min-h-screen">
      <a
        href="#auth-main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        Skip to content
      </a>

      {showcase && (
        <aside className="relative hidden w-[46%] max-w-[40rem] flex-col justify-between overflow-hidden border-r border-border bg-card/40 p-12 lg:flex">
          <Logo size={34} />
          <div className="stagger flex flex-col gap-8">
            <div>
              <h2 className="text-4xl font-semibold leading-[1.1] tracking-[-0.035em]">
                Walk into every interview <span className="text-primary">ready</span>.
              </h2>
              <p className="mt-4 max-w-md text-[15px] leading-7 text-muted-foreground">
                Practise with an interviewer that knows your resume, then get a clear report on what to fix next.
              </p>
            </div>
            <ul className="flex flex-col gap-5">
              {HIGHLIGHTS.map(({ icon: Glyph, title, text }) => (
                <li key={title} className="flex gap-3.5">
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-card text-primary shadow-xs">
                    <Glyph size={18} />
                  </span>
                  <span>
                    <span className="block text-sm font-semibold">{title}</span>
                    <span className="block text-sm leading-6 text-muted-foreground">{text}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldIcon size={14} /> Reports delete themselves after 7 days.
          </p>
        </aside>
      )}

      <div className="relative flex min-w-0 flex-1 flex-col items-center justify-center gap-6 px-4 py-14 sm:px-6">
        <div className="absolute right-4 top-4 sm:right-6 sm:top-6">
          <ThemeToggle />
        </div>
        <Link href="/" className={`rounded-lg ${showcase ? "lg:hidden" : ""}`} aria-label="CyntraAI home">
          <Logo />
        </Link>
        <main id="auth-main" className={`w-full animate-page-in ${wide ? "max-w-lg" : "max-w-sm"}`}>
          {children}
          {footer && (
            <p className="mt-4 text-center text-xs text-muted-foreground">
              <a href="/privacy" className="underline-offset-4 hover:text-foreground hover:underline">
                Privacy
              </a>
            </p>
          )}
        </main>
      </div>
    </div>
  );
}
