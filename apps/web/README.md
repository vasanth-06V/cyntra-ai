# CyntraAI web app

Next.js 16 (App Router, Turbopack), React 19, Tailwind v4, framer-motion, Supabase (auth + row-level security) and a FastAPI backend in `apps/api`. This Next.js version differs from older ones: read the guides in `node_modules/next/dist/docs/` before changing anything framework-specific (see `AGENTS.md`).

## Run

```bash
cp .env.example .env.local   # fill in the values, see below
npm install
npm run dev                  # http://localhost:3000
```

The backend (`apps/api`) must be running at `NEXT_PUBLIC_API_URL` for chat, interviews, ATS and reports.

## Checks

```bash
npx tsc --noEmit     # types (run `npx next typegen` first if LayoutProps is missing)
npx eslint .         # lint
npx vitest run       # unit and component tests (jsdom per file)
npx next build       # production build
```

## Environment variables

See `.env.example`. `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` and `NEXT_PUBLIC_API_URL` are public (inlined at build time). `STORAGE_*` configure the S3-compatible bucket for resumes and are server-only. `NEXT_PUBLIC_ENABLE_DEMO_SIGNUP=true` turns the temporary email sign-up page back on in a production build (it is always on in development).

## Structure

- `app/(auth)` sign-in, account setup, onboarding, temporary demo sign-up.
- `app/(dashboard)` the signed-in app: chat, interviews (setup and room), ATS score, resumes, reports, settings (API keys, team), question bank.
- `app/api/resumes` route handlers for resume upload, rename and delete (Supabase + storage).
- `components/ui` design-system primitives (`Button`, `Card`, `ListRow`, `ConfirmDialog`, `Toast`, ...), `components/<area>` feature components.
- `lib/api-client` bearer-token fetch client for the FastAPI backend (retries reads while the server wakes up).
- `lib/voice` browser speech recognition and synthesis for the interview room.
- `lib/auth/guards.ts` server-side route guards, `proxy.ts` Supabase session refresh.
- `docs/UI_REFRESH.md` and `docs/FRONTEND_GAPS.md` (repo root) describe the design tokens and the established UI patterns.
