import Link from "next/link";
import { requireUser } from "@/lib/auth/guards";
import { Card } from "@/components/ui/Card";
import { ArrowRightIcon, ChatIcon, GaugeIcon, KeyIcon, FileIcon, MicIcon } from "@/components/ui/icons";

const FEATURES = [
  {
    href: "/chat",
    icon: ChatIcon,
    title: "AI Chatbot",
    text: "Chat with any provider you've configured.",
  },
  {
    href: "/interviews",
    icon: MicIcon,
    title: "Interviewing Agent",
    text: "Voice-driven mock interviews, personalized to your resume.",
  },
  {
    href: "/ats-score",
    icon: GaugeIcon,
    title: "ATS Score",
    text: "See how your resume matches a job description.",
  },
];

const STEPS = [
  { href: "/settings/api-keys", icon: KeyIcon, label: "Add an AI key", hint: "Gemini is required" },
  { href: "/settings/resumes", icon: FileIcon, label: "Upload your resume", hint: "PDF or DOCX" },
  { href: "/interviews/setup", icon: MicIcon, label: "Start a mock interview", hint: "About an hour" },
];

export async function DashboardHome() {
  const { role } = await requireUser();

  return (
    <div className="flex flex-col gap-8">
      <section className="brand-wash relative overflow-hidden rounded-2xl border border-border bg-card p-5 shadow-md sm:p-9">
        <p className="text-xs font-medium uppercase tracking-[0.08em] text-primary">Your workspace</p>
        <h1 className="mt-3 max-w-2xl text-[1.75rem] font-semibold leading-[1.1] tracking-[-0.035em] sm:text-[2.6rem]">
          Welcome to CyntraAI
        </h1>
        <p className="mt-3 max-w-xl text-[15px] leading-7 text-muted-foreground">
          Signed in as <span className="font-medium capitalize text-foreground">{role}</span>. Practise, measure, improve: three
          quiet steps to your next offer.
        </p>

        <ol className="stagger mt-7 grid grid-cols-[repeat(auto-fit,minmax(14rem,1fr))] gap-3">
          {STEPS.map(({ href, icon: Glyph, label, hint }, i) => (
            <li key={href}>
              <Link
                href={href}
                className="group flex h-full items-center gap-3 rounded-xl border border-border bg-background/70 p-3.5 backdrop-blur transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md motion-reduce:hover:translate-y-0"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                  <Glyph size={18} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-xs font-medium text-muted-foreground">Step {i + 1}</span>
                  <span className="block truncate text-sm font-semibold">{label}</span>
                  <span className="block truncate text-xs text-muted-foreground">{hint}</span>
                </span>
                <ArrowRightIcon
                  size={16}
                  className="shrink-0 text-muted-foreground transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-primary motion-reduce:transform-none"
                />
              </Link>
            </li>
          ))}
        </ol>
      </section>

      <section aria-label="What you can do">
        <h2 className="mb-3 text-sm font-semibold tracking-tight text-muted-foreground">Your toolkit</h2>
        <div className="stagger grid grid-cols-[repeat(auto-fit,minmax(15rem,1fr))] gap-4">
          {FEATURES.map(({ href, icon: Glyph, title, text }) => (
            <Link key={href} href={href} className="group rounded-xl">
              <Card interactive className="h-full p-5">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-accent-foreground transition-colors duration-200 group-hover:bg-primary group-hover:text-primary-foreground">
                  <Glyph size={20} />
                </span>
                <h3 className="mt-4 font-semibold tracking-tight">{title}</h3>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">{text}</p>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
