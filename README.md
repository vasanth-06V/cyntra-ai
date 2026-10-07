# CyntraAI

A bring-your-own-key AI platform with three tools under one account:

| Tool | What it does |
|---|---|
| **AI Chatbot** | Streamed chat with the provider you have a key for: Gemini, Claude or Groq. Replies render as formatted text. |
| **AI Interviewing Agent** | Timed 60-minute mock interviews in 8 types (Coding, Behavioral, HR, ML/AI, Web Dev, SDE, System Design, Case Study), personalised from your resume and a job description. Type or speak your answers (browser voice), solve coding problems in an editor, then get an on-demand report that stays available for 7 days. |
| **AI Resume ATS Score** | Scores a resume against a job description on keywords, meaning and formatting, with written feedback and a history of your last 10 checks per resume. |

Users add their own LLM API keys, so the platform pays nothing for model usage. The whole stack is designed to run on free tiers (Vercel Hobby, Render free, Supabase free).

> **Status:** feature-complete and covered by automated tests, but not yet deployed. Parts that need a real provider key (interviews, coding review, reports, voice) have been verified with test doubles, not in live use. See [docs/PRODUCT.md](docs/PRODUCT.md) section 7 for exactly what is verified live.

## How it is built

```
apps/web   Next.js 16 (App Router), React 19, Tailwind v4, framer-motion
apps/api   FastAPI (Python 3.13), one worker, background job runner
Supabase   Auth (Google), Postgres + pgvector with row-level security, S3-compatible storage
```

- **Auth and roles:** Google sign-in through Supabase. The first account is the Owner, who can promote Admins; Admins can manage the question bank.
- **BYOK:** each user's provider keys are encrypted at rest (Fernet) and used only for that user's requests.
- **LLM gateway:** one layer for every model call, with per-user rate limits, retries, deadlines, usage accounting and structured-output repair.
- **Resume RAG:** PDF/DOCX parsing, section-aware chunking, Gemini embeddings in pgvector, and a calibrated semantic plus keyword ATS score.
- **Coding round:** the candidate's code is reviewed by one LLM call against a reference solution. Nothing is ever executed.
- **Settings:** account, resumes, API keys, security and team management live under the gear icon in the top bar. Account deletion is its own section.

## Repository map

```
apps/api/app/        FastAPI code (routers, services, llm gateway, rag, ats, interviews, coding, reports, team, account)
apps/api/app/db/     the only package that talks to Supabase
apps/api/migrations/ SQL migrations 0001-0030 (applied in numeric order)
apps/api/scripts/    owner-run tools: question loader, live evaluations, key rotation, deploy check
apps/api/tests/      backend tests (fakes only, no network)
apps/web/app/        pages: (auth) sign-in and onboarding, (dashboard) the signed-in app, api/ route handlers
apps/web/components/ UI primitives and feature components
apps/web/lib/        API client, auth guards, voice, helpers
docs/                product reference, runbooks, plans, audits
render.yaml          Render blueprint for the API
```

## Run it locally

You need Node 22, Python 3.13, and a Supabase project with the migrations applied.

**API**
```bash
cd apps/api
python -m venv venv
venv\Scripts\activate            # Windows; on macOS/Linux: source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env             # fill in the values
python -m uvicorn app.main:app --port 8000
```

**Web**
```bash
cd apps/web
npm install
cp .env.example .env.local       # fill in the values
npm run dev                      # http://localhost:3000
```

The API has no auto-reload; restart it after backend changes. Never commit `.env` or `.env.local`.

## Checks

```bash
# API (from apps/api)
python -m pytest -q

# Web (from apps/web)
npx next typegen && npx tsc --noEmit
npx eslint .
npm test
npx next build
```

CI runs the same checks on every push (`.github/workflows/ci.yml`).

## Deploying

Follow [docs/DEPLOY.md](docs/DEPLOY.md) (Supabase, then Vercel, then Render) and work through [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md) before sharing the URL. After deploying, verify with:

```bash
cd apps/api
python -m scripts.check_deploy https://<your-api> https://<your-web-app>
```

## Documentation

Start with [docs/README.md](docs/README.md), the index of every document. The most useful ones:

- [docs/PRODUCT.md](docs/PRODUCT.md): features, architecture, API inventory, data model, decisions, limitations
- [docs/DEPLOY.md](docs/DEPLOY.md) and [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md): deployment and launch
- [docs/FACTS.md](docs/FACTS.md): external facts the product relies on, each marked verified or unverified
- [docs/PROJECT_DOCUMENTARY.md](docs/PROJECT_DOCUMENTARY.md): the build journal

## Security notes

Secrets live only in environment files and the hosting dashboards. The service-role key belongs to the API alone and must never be added to the web app. Report a security problem privately to the repository owner rather than opening a public issue.
