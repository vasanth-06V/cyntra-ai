# CyntraAI deployment runbook

Status: **DRAFT FOR APPROVAL, written 2026-10-04.** Nothing has been deployed yet. This is a runbook for the owner: you do the clicks, the assistant cannot create accounts or deploy. Facts about Render, Vercel and Supabase limits are published free-plan figures that were not measured on your accounts; they are marked **unverified** where they matter. Read `docs/LAUNCH_CHECKLIST.md` alongside this file; the checklist is what makes the deployment safe to make public.

Targets: Supabase free (database, auth, storage), Render free (the API, `apps/api`), Vercel Hobby (the web app, `apps/web`). Total cost $0/month; LLM costs are paid by each user's own keys.

## 0. Files this runbook depends on (to be written after you approve this document)

None of these exists yet; they are **not** created by this document. The lead will add them, containing exactly this:

| File | Contents |
|---|---|
| `apps/api/Dockerfile` | `FROM python:3.13-slim`; create and switch to a non-root user; `WORKDIR /app`; copy `requirements.txt` and run `pip install --no-cache-dir -r requirements.txt` (the production file, **not** `requirements-dev.txt`); copy `app/` (and `scripts/` so the owner-run tools can be used from a shell if wanted); `CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` with **one worker** (no `--workers`, no `--reload`, no gunicorn with several workers) |
| `apps/api/.dockerignore` | `venv/`, `tests/`, `.env*`, `__pycache__/`, `.pytest_cache/` |
| `render.yaml` (repo root) | one `web` service, `runtime: docker`, `rootDir`/`dockerfilePath` pointing at `apps/api`, `plan: free`, `healthCheckPath: /health` (not `/ready`, so a database blip never restarts the service), `autoDeploy` as you choose, and `envVars` for every backend variable in section 3 with `sync: false` for every secret (so no secret is ever in git), `ENVIRONMENT=production` |
| `scripts/check_deploy.py` | Read-only checker you run from your machine: `GET /health` and `GET /ready` (expect 200), `GET /docs` and `GET /openapi.json` (expect 404), a CORS preflight `OPTIONS /keys` with `Origin: <your Vercel URL>` (expect `access-control-allow-origin` and `allow-credentials`), and a negative preflight from `http://evil.example` (expect no allow-origin). It calls no LLM provider |
| `apps/web/.env.example` | The web variables of section 4 with empty values, plus a `!.env.example` line in `apps/web/.gitignore` (which ignores `.env*`). Both already exist as **uncommitted** working-tree changes at the time of writing; commit them |
| `.gitattributes` | `* text=auto eol=lf` (the repo currently has mixed line endings on Windows) |

Prerequisites before any of this: the repository must be on GitHub (it has **no git remote today**), and the CI web job needs its `tsc` ordering fixed (audit H-02) so the first CI run is not red.

## 1. Supabase (do first)

You already have a project (`erdsnljuppltvmvivugv`, Postgres 17, region ap-south-1) with migrations 0001-0029 applied. Using the same project as production is simplest. Using a fresh project instead requires the steps marked (new project only), and the migration replay in numeric order has **never been tested on an empty database** (audit M-03): treat a new project as an experiment and compare its catalog with the live one afterwards.

1. (new project only) Apply `apps/api/migrations/0001` ... `0029` in numeric order using the SQL editor. If a hardening migration (`0030`) has been approved and applied on the existing project, apply it on a new project too. `0007` needs the `extensions` schema that Supabase provides.
2. Storage bucket (new project only; the existing project has it): create a **private** bucket named `resumes`, file size limit 500 KB (512000 bytes), allowed MIME types `application/pdf` and `application/vnd.openxmlformats-officedocument.wordprocessingml.document`. Add **no** policies on `storage.objects`: all access is server-side through the S3 key.
3. S3 credentials: Project Settings > Storage > S3 Connection. Note the endpoint URL, region and create an access key (id + secret). These are project-wide, not bucket-scoped. You need them for both Render and Vercel.
4. Authentication > Providers > Google: already enabled for development. The Google OAuth client keeps using Supabase's own callback URL, so nothing changes in Google Cloud.
5. Authentication > URL Configuration: set **Site URL** to your Vercel URL (section 5 step 4) and add the same URL to **Redirect URLs** (the web app sends users to `<origin>/auth/callback`). Keep `http://localhost:3000` in the list while you still develop locally.
6. Authentication settings to apply at launch (details in the checklist): disable email sign-ups once the demo sign-up is gone, and turn on leaked-password protection (may need a paid plan; unverified).
7. **The first account to sign in becomes the Owner** (database trigger on profile creation). Sign in yourself first, before sharing the URL with anyone.
8. Copy these values for later (do not paste them into chat or commit them): project URL, `service_role` key (secret), anon key (public), JWT secret (secret; only needed as an HS256 fallback), S3 endpoint/region/access key id/secret.

## 2. Order of deployment

Because each side needs the other's URL, use this order:

1. Supabase prepared (section 1, without the Site URL yet).
2. Vercel: import the repo and deploy once (the build only needs the three `NEXT_PUBLIC_*` values to exist; use a placeholder for `NEXT_PUBLIC_API_URL`). You now know the web URL.
3. Render: create the API with `CORS_ORIGINS` set to the Vercel URL. You now know the API URL.
4. Vercel: set `NEXT_PUBLIC_API_URL` to the Render URL and **redeploy** (`NEXT_PUBLIC_*` values are baked into the build; changing them needs a new build).
5. Supabase: set Site URL and Redirect URLs to the Vercel URL.
6. Verify (section 6).

## 3. Render (API)

1. New > Web Service > connect the GitHub repo (or Blueprint, once `render.yaml` exists). Runtime Docker, root `apps/api`, free instance type, health check path `/health`. **Run exactly one instance and one worker**: the rate limiter, throttles, caches, job runner (6 concurrent jobs), turn locks and the report sweeper are all per process; a second worker would multiply limits and break job recovery. The free plan has one instance, so just never add `--workers` and never scale up.
2. Environment variables (`apps/api/.env.example` is the template):

| Variable | Secret | Where the value comes from | Notes |
|---|---|---|---|
| `SUPABASE_URL` | no | Supabase > Project Settings > API | |
| `SUPABASE_SERVICE_ROLE_KEY` | **yes** | same page, `service_role` key | Bypasses RLS: never put it in the web app |
| `SUPABASE_JWT_SECRET` | **yes** | Project Settings > API > JWT secret | Optional; blank means HS256 tokens are refused (ES256 via JWKS keeps working) |
| `KEY_ENCRYPTION_SECRET` | **yes** | **Your existing value** (copy it from `apps/api/.env`) | One Fernet key, or several comma-separated. If you generate a new one, every saved user API key becomes unreadable; to rotate safely use `scripts/rotate_keys.py` (see the checklist) |
| `STORAGE_ENDPOINT_URL` | no | Supabase S3 Connection | Required in production |
| `STORAGE_REGION` | no | Supabase S3 Connection | Default `us-east-1` if blank |
| `STORAGE_ACCESS_KEY_ID` | **yes** | Supabase S3 access key | Required in production |
| `STORAGE_SECRET_ACCESS_KEY` | **yes** | Supabase S3 access key | Required in production |
| `STORAGE_BUCKET_NAME` | no | `resumes` | Required in production |
| `ENVIRONMENT` | no | set to `production` | See the warning below |
| `CORS_ORIGINS` | no | Your Vercel URL, exact origin with `https://` and no trailing slash; several allowed, comma-separated | Production refuses to boot if it is empty or contains `localhost` |
| `PORT` | no | Provided by Render | The container command reads it |

3. **Warning: `ENVIRONMENT` defaults to `development`.** If you forget `ENVIRONMENT=production`, the API still starts, but the interactive docs and OpenAPI schema (`/docs`, `/redoc`, `/openapi.json`) stay **open to the world**, localhost CORS is not rejected and the production configuration checks are skipped. Verify with section 6 step 3 after every deploy.
4. If a required variable is missing or invalid, the service refuses to boot and the log lists each problem ("Invalid configuration"): fix and redeploy.
5. Provider keys (Gemini, Groq, Claude) are **not** server environment variables: each user stores their own in the app. The `GEMINI_API_KEY` / `GROQ_API_KEY` / `ANTHROPIC_API_KEY` variables exist only for owner-run scripts on your own machine.

## 4. Vercel (web)

1. Add New Project > import the repo. **Root Directory `apps/web`**, framework Next.js, Node 22 (CI uses 22). Build and install commands: defaults.
2. Environment variables:

| Variable | Secret | Where the value comes from | Notes |
|---|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | no (public by design) | Supabase project URL | Baked into the build |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | no (public by design; RLS is the guard) | Supabase anon key | Baked into the build |
| `NEXT_PUBLIC_API_URL` | no | The Render URL, **no trailing slash** | Baked into the build: redeploy after changing |
| `STORAGE_ENDPOINT_URL` | no | Supabase S3 Connection | Server-only |
| `STORAGE_REGION` | no | same | Server-only |
| `STORAGE_ACCESS_KEY_ID` | **yes** | same | Server-only (`lib/storage.ts` imports `server-only`); mark as sensitive |
| `STORAGE_SECRET_ACCESS_KEY` | **yes** | same | Server-only; mark as sensitive |
| `STORAGE_BUCKET_NAME` | no | `resumes` | Server-only |
| `NEXT_PUBLIC_ENABLE_DEMO_SIGNUP` | no | leave **unset** in production | Build-time switch read by `apps/web/lib/demo-signup.ts`: the demo sign-up page is on in development and **off in production builds unless this is exactly `true`**. That file is **uncommitted** at the time of writing and was not verified by this document; at HEAD no code reads the variable and the page ships. Deleting the route and its link is the safer launch step (see the checklist) |

Never add `SUPABASE_SERVICE_ROLE_KEY` to Vercel: the web app does not need it. Vercel limits (published figures, unverified for your account): 4.5 MB request body cap (resumes are limited to 500 KB), 300 s Hobby function duration (a resume upload waits for processing inside the function).
3. Deploy, then note the production URL (`https://<project>.vercel.app`). If you add a custom domain later, add it to `CORS_ORIGINS` (comma-separated) and to Supabase's Redirect URLs.
4. Security headers: at HEAD the app sends none (audit M-1). An uncommitted `next.config.ts` change adds a conservative set; after deploying check them with `curl -I https://<vercel-url>/sign-in` (see the checklist).

## 5. Keep-warm (optional)

Render's free service sleeps after about 15 minutes without traffic and takes about a minute to wake (published figures; not measured here). The web app shows a "Waking the server..." banner and retries, so everything works without keep-warm; the first visit is just slow. A job in flight when a cold instance restarts is marked failed (boot recovery), so users can lose a running interview setup, code review or report if the instance restarts mid-job.

Option: a free uptime monitor (for example UptimeRobot or Better Stack, any equivalent) requesting `https://<render-url>/ready` every 5-10 minutes. That keeps Render awake (one always-on service uses about 744 of the 750 free instance-hours a month; a second always-on service would not fit) and gives you an alert when the database is unreachable or paused. `/ready` reads the database, so it also generates database traffic; whether that prevents a Supabase free-tier pause is **unverified**. Use `/health` instead if you want a check that never touches the database.

## 6. Verify the deployment

Once `scripts/check_deploy.py` exists, run it. Until then, by hand (replace the two URLs):

1. `curl -i https://<render-url>/health` returns 200 `{"status":"ok"}`; the first call after idle can take about a minute.
2. `curl -i https://<render-url>/ready` returns 200 `{"status":"ready"}`. A 503 `{"status":"unavailable"}` means the database is unreachable (see section 7).
3. `curl -i https://<render-url>/docs` and `/openapi.json` must return **404**. If they return 200, `ENVIRONMENT` is not `production`.
4. CORS from your site: `curl -i -X OPTIONS https://<render-url>/keys -H "Origin: https://<vercel-url>" -H "Access-Control-Request-Method: GET" -H "Access-Control-Request-Headers: authorization"` must include `access-control-allow-origin: https://<vercel-url>`. The same request with `Origin: http://evil.example` must **not** include an allow-origin header.
5. In a private browser window open the Vercel URL, sign in with Google (you become the Owner if you are the first account), add your Gemini key, send a chat message, upload a small resume, run an ATS check. Then follow the walk-through in `docs/LAUNCH_CHECKLIST.md`.
6. Check the Render log: JSON lines with a request id, no stack traces at startup.

## 7. When the Supabase free project pauses

Free Supabase projects pause after about a week of inactivity (published rule; confirm in your dashboard). Symptoms: `/ready` returns 503, every page errors, sign-in fails. Fix: Supabase dashboard > the project > **Restore/Resume project**, wait until it is healthy, then call `/ready` again; the API needs no restart (it talks to Supabase over HTTP; unverified). How long a paused project can be restored is **unverified**: check the dashboard and do not leave it paused for months. To avoid pauses, use the uptime monitor from section 5 or sign in regularly.

## 8. Rollback

- **Web (Vercel):** Deployments > pick the last good deployment > Promote to Production (instant, no rebuild).
- **API (Render):** Events/Deploys > roll back to a previous deploy, or redeploy the previous commit. Environment variable changes need a redeploy to take effect.
- **Database:** there are no down-migrations. Rolling back a migration means writing and applying a new forward migration, only with the owner's go-ahead. Before applying any migration to production, take a manual export (for example `pg_dump` with the connection string from Project Settings > Database); whether the free plan offers automatic backups or point-in-time restore is **unverified**.
- **Secrets:** to revoke a leaked secret, rotate it at the source (Supabase keys, S3 key) and update Render/Vercel; for `KEY_ENCRYPTION_SECRET` use the documented rotation (`KEY_ENCRYPTION_SECRET=<new>,<old>`, restart, `python -m scripts.rotate_keys --apply`, then remove `<old>`).

## 9. Known limits of this deployment

One instance and one worker; free-tier cold starts; a deploy or restart fails jobs that are mid-flight (boot recovery fails every active job, audit M-04); Gemini quotas are per Google project of each user's key; Supabase free storage is 1 GB and the database 500 MB (the live database is 12 MB today). See `docs/PRODUCT.md` section 7.3.
