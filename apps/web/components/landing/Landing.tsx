import Link from "next/link";
import type { CSSProperties } from "react";
import { Bricolage_Grotesque, Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import { LogoMark } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { LandingEffects } from "./LandingEffects";
import "./landing.css";

const display = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-bricolage", display: "swap" });
const body = Hanken_Grotesk({ subsets: ["latin"], variable: "--font-hanken", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains", display: "swap" });

const delay = (i: number) => ({ "--i": i }) as CSSProperties;

function Icon({ id, size = 16, className = "" }: { id: string; size?: number; className?: string }) {
  return (
    <svg className={`ico ${className}`.trim()} width={size} height={size} aria-hidden="true">
      <use href={`#i-${id}`} />
    </svg>
  );
}

const TYPES: { icon: string; label: string }[] = [
  { icon: "code", label: "Coding" },
  { icon: "chat", label: "Behavioral" },
  { icon: "eye", label: "HR" },
  { icon: "chart", label: "ML / AI" },
  { icon: "code", label: "Web Dev" },
  { icon: "code", label: "SDE" },
  { icon: "chart", label: "System Design" },
  { icon: "doc", label: "Case Study" },
];

const FACTS = [
  { n: 8, label: "interview types" },
  { n: 60, label: "minute sessions" },
  { n: 3, label: "AI providers" },
  { n: 7, label: "day reports" },
];

const REQS: { name: string; ok: boolean }[] = [
  { name: "PostgreSQL", ok: true },
  { name: "REST API design", ok: true },
  { name: "Python", ok: true },
  { name: "Caching", ok: true },
  { name: "Docker", ok: false },
];

const STEPS = [
  {
    title: "Add your AI key",
    text: "Paste a free Gemini key from Google AI Studio. Add Groq or Claude too if you have them. It is checked and stored encrypted.",
  },
  {
    title: "Upload your resume",
    text: "PDF or DOCX, up to 500 KB, and up to three resumes per account. It is read and indexed in a minute or so.",
  },
  {
    title: "Practice and measure",
    text: "Run an ATS check against a job post, start an interview, then open your report. Repeat after each edit.",
  },
];

const TRUST = [
  { icon: "lock", title: "Keys are encrypted", text: "Provider keys are encrypted before they are stored and used only for your own requests." },
  { icon: "eye", title: "Private by default", text: "Your resumes, chats and interviews are visible only to your account." },
  { icon: "clock", title: "Reports expire", text: "Interview reports are deleted automatically after 7 days. You can delete one sooner." },
  { icon: "trash", title: "Delete everything", text: "One page in Settings removes your profile, resumes, files, keys and history." },
];

const FAQ = [
  {
    q: "Do I have to pay?",
    a: "CyntraAI does not charge you. The AI calls are made with your own key, so usage counts against your own provider account. A free Gemini key is enough to begin.",
  },
  {
    q: "How many AI calls does an interview use?",
    a: "A full hour comes to roughly 40 model calls: one to set it up, one for each answer you give, a short summary every few answers, and one more if you ask for a report. The exact count depends on how many answers you give.",
  },
  {
    q: "Is my code from the coding round run?",
    a: "No. The AI compares your logic with a reference solution and tells the interviewer how it went. Nothing is executed.",
  },
  {
    q: "Which browsers support voice?",
    a: "Voice answers need speech recognition, which Chrome and Edge provide. In other browsers you can type, and everything else works the same.",
  },
  {
    q: "Which AI providers work?",
    a: "Gemini, Claude and Groq. A Gemini key is required to begin, and interviews run on Gemini or Groq.",
  },
  {
    q: "Can I remove my data?",
    a: "Yes. You can delete single resumes, chats, interviews and reports, or delete your whole account from Settings.",
  },
];

function Sprite() {
  const stroke = { fill: "none", stroke: "currentColor", strokeLinecap: "round", strokeLinejoin: "round" } as const;
  return (
    <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="lp-spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#7c3aed" stopOpacity=".3" />
          <stop offset="1" stopColor="#7c3aed" stopOpacity="0" />
        </linearGradient>
        <symbol id="i-check" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" {...stroke} strokeWidth="2.4" /></symbol>
        <symbol id="i-x" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18" {...stroke} strokeWidth="2.4" /></symbol>
        <symbol id="i-arrow" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" {...stroke} strokeWidth="2.2" /></symbol>
        <symbol id="i-mic" viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3" fill="none" stroke="currentColor" strokeWidth="1.9" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" {...stroke} strokeWidth="1.9" /></symbol>
        <symbol id="i-code" viewBox="0 0 24 24"><path d="M8 7l-5 5 5 5M16 7l5 5-5 5M13.5 5l-3 14" {...stroke} strokeWidth="1.9" /></symbol>
        <symbol id="i-doc" viewBox="0 0 24 24"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5z" {...stroke} strokeWidth="1.9" /><path d="M14 3v5h5M9 13h6M9 17h4" {...stroke} strokeWidth="1.9" /></symbol>
        <symbol id="i-chart" viewBox="0 0 24 24"><path d="M4 19V5M4 19h16M8 15l3-4 3 2 5-7" {...stroke} strokeWidth="1.9" /></symbol>
        <symbol id="i-key" viewBox="0 0 24 24"><circle cx="8" cy="15" r="4" fill="none" stroke="currentColor" strokeWidth="1.9" /><path d="M11 12l9-9M16 7l3 3" {...stroke} strokeWidth="1.9" /></symbol>
        <symbol id="i-lock" viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="10" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.9" /><path d="M8 11V8a4 4 0 0 1 8 0v3" {...stroke} strokeWidth="1.9" /></symbol>
        <symbol id="i-eye" viewBox="0 0 24 24"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" fill="none" stroke="currentColor" strokeWidth="1.9" /><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="1.9" /></symbol>
        <symbol id="i-clock" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.9" /><path d="M12 7v5l3 2" {...stroke} strokeWidth="1.9" /></symbol>
        <symbol id="i-trash" viewBox="0 0 24 24"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" {...stroke} strokeWidth="1.9" /></symbol>
        <symbol id="i-chat" viewBox="0 0 24 24"><path d="M20 12a8 8 0 0 1-11.6 7.1L4 20l1-3.9A8 8 0 1 1 20 12z" {...stroke} strokeWidth="1.9" /></symbol>
        <symbol id="i-mark" viewBox="0 0 64 64">
          <g fill="none" stroke="currentColor" strokeWidth="5.4" strokeLinecap="round">
            <path opacity=".42" d="M45.43 13.62A24 24 0 1 0 45.43 50.38" />
            <path opacity=".72" d="M40.61 19.36A16.5 16.5 0 1 0 40.61 44.64" />
            <path d="M35.78 25.11A9 9 0 1 0 35.78 38.89" />
          </g>
        </symbol>
      </defs>
    </svg>
  );
}

function Ring({ label }: { label: string }) {
  return (
    <svg className="ring" viewBox="0 0 64 64" role="img" aria-label={label}>
      <circle cx="32" cy="32" r="27" fill="none" stroke="var(--surface-2)" strokeWidth="7" />
      <circle className="fg" cx="32" cy="32" r="27" fill="none" stroke="var(--accent)" strokeWidth="7" strokeLinecap="round" />
      <text x="32" y="38" textAnchor="middle" fontSize="19">80</text>
    </svg>
  );
}

function Chrome({ title, timer }: { title: string; timer?: string }) {
  return (
    <div className="chrome">
      <i /><i /><i />
      <span className="t">{title}</span>
      {timer && <span className="timer" aria-label="38 minutes 12 seconds left">{timer}</span>}
    </div>
  );
}

export function Landing() {
  return (
    <div className={`lp ${display.variable} ${body.variable} ${mono.variable}`}>
      <Sprite />
      <LandingEffects />

      <header className="top" id="topbar">
        <div className="wrap">
          <a className="brand" href="#top" aria-label="CyntraAI home">
            <LogoMark size={32} />
            <span>Cyntra<b>AI</b></span>
          </a>
          <nav className="nav" aria-label="Page sections">
            <a href="#products">Products</a>
            <a href="#features">Features</a>
            <a href="#how">How it works</a>
            <a href="#trust">Your data</a>
            <a href="#faq">FAQ</a>
          </nav>
          <div className="top-cta">
            <ThemeToggle />
            <Link className="btn btn-ghost btn-sm" href="/sign-in">Sign in</Link>
            <Link className="btn btn-primary btn-sm" href="/sign-in">Get started</Link>
          </div>
        </div>
      </header>

      <main id="top">
        {/* ================= HERO ================= */}
        <div className="hero" id="hero">
          <div className="grid-bg" aria-hidden="true" />
          <div className="orb o1" aria-hidden="true" />
          <div className="orb o2" aria-hidden="true" />
          <div className="wrap hero-grid">
            <div>
              <p className="eyebrow rise">Interview practice and resume scoring</p>
              <h1 className="rise d1">
                Rehearse the interview. <span className="hl">Fix the resume.</span> Use your own AI key.
              </h1>
              <p className="lede rise d2">
                CyntraAI runs timed mock interviews built from your resume and a real job post, scores your resume the way
                an applicant tracking system would, and answers questions in a chat. Everything runs on a key you bring, so
                there is no subscription.
              </p>
              <div className="actions rise d3">
                <Link className="btn btn-primary btn-lg" href="/sign-in">
                  Get started free <Icon id="arrow" size={18} className="arrow" />
                </Link>
                <a className="btn btn-ghost btn-lg" href="#products">See it in action</a>
              </div>
              <p className="fine rise d3">
                {["Sign in with Google", "Free Gemini key works", "No card needed"].map((t) => (
                  <span key={t}><Icon id="check" />{t}</span>
                ))}
              </p>
              <ul className="facts rise d4" aria-label="At a glance">
                {FACTS.map((f) => (
                  <li key={f.label}><strong data-to={f.n}>{f.n}</strong>{f.label}</li>
                ))}
              </ul>
            </div>

            <div className="stack" id="stack">
              <span className="tag">Example screen</span>
              <div className="tilt" id="tilt">
                <div className="card mock glow">
                  <Chrome title="interview / behavioral" timer="38:12 left" />
                  <div className="chat">
                    <div className="msg ai"><small>Interviewer</small>You cut API latency in your last project. What was the baseline, and how did you measure the change?</div>
                    <div className="msg me"><small>You</small>The p95 was about 900 ms. I batched the queries, added a cache, and compared p95 over a week of traffic.</div>
                    <div className="msg ai"><small>Interviewer</small>Which of those two changes gave you most of the gain?</div>
                  </div>
                  <div className="voice">
                    <span className="wave" aria-hidden="true">
                      {[0, 1, 2, 3, 4, 5, 6].map((i) => <i key={i} style={delay(i)} />)}
                    </span>
                    Listening. Answer out loud, or type.
                  </div>
                </div>
              </div>
              <div className="card score-card">
                <div className="score-row">
                  <Ring label="Example score 80 out of 100" />
                  <p><b>Resume match</b>4 of 5 must-haves covered. Missing: Docker.</p>
                </div>
                <div className="bars" aria-hidden="true">
                  <div className="bar"><span>Keywords</span><i style={{ "--w": "72%" } as CSSProperties} /></div>
                  <div className="bar"><span>Meaning</span><i style={{ "--w": "84%" } as CSSProperties} /></div>
                  <div className="bar"><span>Format</span><i style={{ "--w": "90%" } as CSSProperties} /></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ================= TICKER ================= */}
        <div className="ticker" aria-label="Interview types">
          <div className="track">
            {[false, true].map((hidden) => (
              <ul key={String(hidden)} aria-hidden={hidden || undefined}>
                {TYPES.map((t) => (
                  <li key={t.label}><Icon id={t.icon} />{t.label}</li>
                ))}
              </ul>
            ))}
          </div>
        </div>

        {/* ================= PRODUCTS (tabs) ================= */}
        <section id="products">
          <div className="wrap">
            <div className="head reveal">
              <p className="eyebrow">Three tools, one account</p>
              <h2>Practice, measure, and ask, in one place.</h2>
              <p>Add your resume once. The interviewer, the scorer and the chat all work from it.</p>
            </div>

            <div className="tabs reveal" role="tablist" aria-label="Products">
              <button className="tab" role="tab" id="tab-0" aria-controls="panel-0" aria-selected="true" type="button">
                <Icon id="mic" size={18} />Interviewing Agent<span className="prog" aria-hidden="true" />
              </button>
              <button className="tab" role="tab" id="tab-1" aria-controls="panel-1" aria-selected="false" tabIndex={-1} type="button">
                <Icon id="chart" size={18} />ATS Score<span className="prog" aria-hidden="true" />
              </button>
              <button className="tab" role="tab" id="tab-2" aria-controls="panel-2" aria-selected="false" tabIndex={-1} type="button">
                <Icon id="chat" size={18} />AI Chatbot<span className="prog" aria-hidden="true" />
              </button>
            </div>

            <div className="stage">
              {/* Panel 0: interviews */}
              <div className="panel show" id="panel-0" role="tabpanel" aria-labelledby="tab-0">
                <div className="copy">
                  <h3>A one-hour interview that reads your resume first.</h3>
                  <p>Paste a job description, pick a resume, and the interviewer builds its questions around both. It moves through phases on a clock, like a real loop.</p>
                  <ul className="ticks">
                    <li><Icon id="check" size={24} /><span><strong>Talk or type.</strong> Voice runs in your browser (Chrome or Edge), with a pause to edit before an answer is sent.</span></li>
                    <li><Icon id="check" size={24} /><span><strong>A real coding round.</strong> Write code in an editor, in any language. One submit per problem.</span></li>
                    <li><Icon id="check" size={24} /><span><strong>A report with evidence.</strong> Scores by skill, quotes from your own answers, and next steps.</span></li>
                  </ul>
                </div>
                <div className="visual">
                  <div className="card vcard glow">
                    <Chrome title="example session" />
                    <div className="vbody">
                      <div className="phases" aria-label="Interview phases">
                        <span className="done"><i />Warm-up</span>
                        <span className="now"><i />Questions</span>
                        <span><i />Wrap-up</span>
                      </div>
                      <div className="chat" style={{ padding: "18px 0 0" }}>
                        <div className="msg ai"><small>Interviewer</small>Walk me through how you would find the slowest query in a service you did not write.</div>
                        <div className="msg me"><small>You</small>I would start from the slow-query log, then look at the plan for the worst one.</div>
                        <div className="msg ai"><small>Interviewer</small><span className="typing" aria-label="Typing"><i /><i /><i /></span></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Panel 1: ATS */}
              <div className="panel" id="panel-1" role="tabpanel" aria-labelledby="tab-1" hidden>
                <div className="copy">
                  <h3>See what a screening system sees.</h3>
                  <p>Paste a job description and get a score built from three parts: the keywords the posting asks for, how closely your experience matches in meaning, and whether your file reads cleanly.</p>
                  <ul className="ticks">
                    <li><Icon id="check" size={24} /><span><strong>Covered or missing.</strong> Every requirement is checked, with the line of your resume that covers it.</span></li>
                    <li><Icon id="check" size={24} /><span><strong>Advice you can act on.</strong> Short tips that name the gaps, without pushing you to claim skills you do not have.</span></li>
                    <li><Icon id="check" size={24} /><span><strong>A history per resume.</strong> Your last 10 checks are saved, so you can see whether an edit helped.</span></li>
                  </ul>
                </div>
                <div className="visual">
                  <div className="card vcard glow">
                    <Chrome title="example result" />
                    <div className="vbody">
                      <div className="score-row">
                        <Ring label="Example score 80 out of 100" />
                        <p><b>Senior backend role</b>4 of 5 must-haves, 6 of 10 nice-to-haves</p>
                      </div>
                      <ul className="reqs">
                        {REQS.map((r) => (
                          <li key={r.name} className={r.ok ? "yes" : "no"}>
                            <Icon id={r.ok ? "check" : "x"} size={18} />{r.name}
                            <span className="st">{r.ok ? "COVERED" : "MISSING"}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              </div>

              {/* Panel 2: Chat */}
              <div className="panel" id="panel-2" role="tabpanel" aria-labelledby="tab-2" hidden>
                <div className="copy">
                  <h3>Ask anything, with the model you choose.</h3>
                  <p>Chat with Gemini, Claude or Groq, whichever key you have added. Answers stream in as formatted text, with headings, lists, tables and code you can copy.</p>
                  <ul className="ticks">
                    <li><Icon id="check" size={24} /><span><strong>Your conversations stay yours.</strong> Rename them, copy any reply, or delete a chat whenever you like.</span></li>
                    <li><Icon id="check" size={24} /><span><strong>Switch providers.</strong> Keep a Gemini key as your base and add Groq or Claude when you want them.</span></li>
                  </ul>
                </div>
                <div className="visual">
                  <div className="card vcard glow">
                    <Chrome title="example chat" />
                    <div className="stream">
                      <div className="row"><b>You</b><span>Give me three STAR tips, and a line to log them.</span></div>
                      <div className="row">
                        <b>Gemini</b>
                        <div className="reply">
                          <p><strong>1. Situation.</strong> One sentence of context.</p>
                          <p><strong>2. Action.</strong> Say what <em>you</em> did, not the team.</p>
                          <p><strong>3. Result.</strong> End with a number or an outcome.<span className="caret" aria-hidden="true" /></p>
                        </div>
                      </div>
                      <pre>{'tips.append("result: p95 900ms -> 310ms")'}</pre>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ================= FEATURES (bento) ================= */}
        <section id="features" style={{ paddingTop: 20 }}>
          <div className="wrap">
            <div className="head reveal">
              <p className="eyebrow">The details that matter</p>
              <h2>Built for the whole prep loop.</h2>
            </div>
            <div className="bento">
              <article className="card tile glow t-voice reveal">
                <div className="row">
                  <div>
                    <div className="badge"><Icon id="mic" size={22} /></div>
                    <h3>Answer out loud, like the real thing</h3>
                    <p>Speak your answers and hear the interviewer reply. Pause to edit before sending, change the speed or voice, and fall back to typing at any moment.</p>
                  </div>
                  <div className="bigwave" aria-hidden="true">
                    {Array.from({ length: 16 }, (_, i) => <i key={i} style={delay(i)} />)}
                  </div>
                </div>
              </article>

              <article className="card tile glow t-code reveal">
                <div className="badge"><Icon id="code" size={22} /></div>
                <h3>Code reviewed, never run</h3>
                <p>The AI compares your logic with a reference solution. Nothing executes, so there is nothing to set up.</p>
              </article>

              <article className="card tile glow t-report reveal">
                <div className="badge"><Icon id="clock" size={22} /></div>
                <h3>Reports that expire</h3>
                <p>Download one or print it as a PDF. It deletes itself after 7 days.</p>
                <div className="meter" aria-hidden="true">
                  <div className="days"><i /><i /><i /><i /><i /><i /><i /></div>
                  <small>EXAMPLE: DAY 3 OF 7</small>
                </div>
              </article>

              <article className="card tile glow t-hist reveal" id="hist">
                <div className="badge"><Icon id="chart" size={22} /></div>
                <h3>See your score climb</h3>
                <p>Each resume keeps its last 10 checks.</p>
                <svg className="spark" viewBox="0 0 200 74" preserveAspectRatio="none" role="img" aria-label="Example: scores rising across ten checks">
                  <path className="fillarea" d="M0 62 L22 58 L44 55 L66 51 L88 53 L111 44 L133 38 L155 32 L177 24 L200 14 L200 74 L0 74 Z" />
                  <path className="ln" d="M0 62 L22 58 L44 55 L66 51 L88 53 L111 44 L133 38 L155 32 L177 24 L200 14" />
                </svg>
              </article>

              <article className="card tile glow t-keys reveal">
                <div className="badge"><Icon id="key" size={22} /></div>
                <h3>Your keys stay locked</h3>
                <p>Keys are encrypted before they are stored, and never shown again.</p>
                <div className="keys" aria-hidden="true">
                  {["Gemini", "Groq"].map((n) => (
                    <div key={n}>{n} <b>{"•".repeat(8)}</b><Icon id="check" /></div>
                  ))}
                </div>
              </article>
            </div>
          </div>
        </section>

        {/* ================= HOW ================= */}
        <section id="how" className="how">
          <div className="wrap">
            <div className="head reveal">
              <p className="eyebrow">Getting started</p>
              <h2>Three steps, about ten minutes.</h2>
            </div>
            <ol className="steps">
              {STEPS.map((s) => (
                <li className="card reveal" key={s.title}>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </li>
              ))}
            </ol>
            <p style={{ marginTop: 36 }}>
              <Link className="btn btn-primary btn-lg" href="/sign-in">
                Start with Google <Icon id="arrow" size={18} className="arrow" />
              </Link>
            </p>
          </div>
        </section>

        {/* ================= TRUST ================= */}
        <section id="trust">
          <div className="wrap">
            <div className="head reveal">
              <p className="eyebrow">Bring your own key</p>
              <h2>Your key, your data, your call.</h2>
              <p>Because the AI usage runs on your own account, we never pay for it, and we never need to charge you for it.</p>
            </div>
            <div className="trust-grid">
              {TRUST.map((t) => (
                <div className="reveal" key={t.title}>
                  <Icon id={t.icon} size={40} />
                  <h3>{t.title}</h3>
                  <p>{t.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ================= FAQ ================= */}
        <section id="faq" style={{ paddingTop: 20 }}>
          <div className="wrap">
            <div className="head reveal">
              <p className="eyebrow">Questions</p>
              <h2>Before you start.</h2>
            </div>
            <div className="faq reveal">
              {FAQ.map((f) => (
                <details key={f.q}>
                  <summary>{f.q}</summary>
                  <p>{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* ================= CLOSING ================= */}
        <div className="closing">
          <div className="wrap">
            <div className="card cta reveal">
              <svg className="mark" viewBox="0 0 64 64" aria-hidden="true"><use href="#i-mark" /></svg>
              <div>
                <h2>Your next interview is already on the calendar. Practice it first.</h2>
                <p>Sign in with Google, add a key, and run your first mock interview today.</p>
              </div>
              <Link className="btn btn-primary btn-lg" href="/sign-in">
                Get started free <Icon id="arrow" size={18} className="arrow" />
              </Link>
            </div>
          </div>
        </div>
      </main>

      <footer>
        <div className="wrap">
          <span>&copy; 2026 CyntraAI</span>
          <nav aria-label="Footer">
            <a href="#products">Products</a>
            <a href="#features">Features</a>
            <a href="#how">How it works</a>
            <a href="#faq">FAQ</a>
            <Link href="/privacy">Privacy</Link>
            <Link href="/sign-in">Sign in</Link>
          </nav>
        </div>
      </footer>

      <div className="sticky-cta" id="sticky">
        <Link className="btn btn-primary btn-lg" href="/sign-in">
          Get started free <Icon id="arrow" size={18} className="arrow" />
        </Link>
      </div>
    </div>
  );
}
