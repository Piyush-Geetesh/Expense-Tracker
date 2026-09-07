# Render + Neon + Vercel

The production path is:

Browser -> Vercel Next.js -> /api/ proxy -> Render Django -> existing Neon database.

Your public UI remains https://expense-tracker-lemon-omega-49.vercel.app.
Render hosts only Django. Register at the Vercel URL /register, not at the Render URL.
The old Django root intentionally returns 410; use /health/ to verify the backend.

## Files and secrets

- Root .env: local Django configuration, now loaded automatically. Existing shell variables win.
- .env.example: local reference.
- .env.render.example: reference for Render's Environment page.
- frontend/.env.local: local Next.js configuration, loaded automatically.
- frontend/.env.vercel.example: reference for Vercel's Environment page.
- Actual .env files are ignored by Git. Never commit the Neon connection string or Django secret.

The hosting platforms need values in their Environment settings. A committed example file does not configure the live service.

## 1. Preserve Neon first

Keep the existing Neon project, database, and production branch. Do not create an empty replacement and assume the old expenses will follow.

Before applying schema changes, create a backup/recovery point or a separate Neon branch and rehearse the migration there. Review [MIGRATION.md](MIGRATION.md). Existing unowned salary/expense rows are retained but hidden from new user accounts until explicitly mapped.

Use the same production database connection that the old Django deployment used. Copy it directly from Neon or the old hosting environment into Render as DATABASE_URL; do not put it in chat or frontend variables. Include sslmode=require. Use the direct Neon connection for this small service, with the same database and role.

## 2. Deploy Django to Render

Connect GitHub repository Piyush-Geetesh/Expense-Tracker. The Render deployment files must be committed and pushed before Render can build them.

The root render.yaml Blueprint defines a free Python web service and prompts for DATABASE_URL. It does not create a database. Alternatively create a Web Service manually:

| Setting | Value |
| --- | --- |
| Root Directory | Leave empty (repository root) |
| Runtime | Python 3 |
| Build Command | bash build.sh |
| Start Command | bash start.sh |
| Health Check Path | /health/ |
| Instance | Free for initial verification |
| Auto Deploy | Off while performing the initial migration/cutover |

Set these Render environment variables:

| Name | Value |
| --- | --- |
| PYTHON_VERSION | 3.12.13 |
| DEBUG | False |
| DJANGO_READ_DOTENV | False |
| DJANGO_SECRET_KEY | Generate a strong random value; the Blueprint generates it |
| DATABASE_URL | Existing Neon PostgreSQL URL, including sslmode=require |
| DJANGO_CSRF_TRUSTED_ORIGINS | https://expense-tracker-lemon-omega-49.vercel.app |
| DJANGO_TRUST_PROXY | True |
| RUN_MIGRATIONS | False initially |
| WEB_CONCURRENCY | 2 |

Render supplies RENDER_EXTERNAL_HOSTNAME automatically. Django adds that exact hostname to ALLOWED_HOSTS. If you add a custom backend hostname, put it in DJANGO_ALLOWED_HOSTS too. No wildcard is necessary.

Build installs dependencies and collects static files only. WhiteNoise serves Django admin static assets; Gunicorn runs the WSGI application.

### Initial schema update

start.sh checks whether migrations are applied before starting Gunicorn. If the database is still on the old schema, it fails clearly rather than serving broken API requests.

After backup, rehearsal, and approval to apply the reviewed migrations:
1. Set RUN_MIGRATIONS=True.
2. Deploy once. The startup script applies migrations and then starts Gunicorn.
3. Confirm /health/ returns HTTP 200 and /api/auth/csrf/ returns JSON.
4. Set RUN_MIGRATIONS=False for later deploys.

If an existing process is still writing old-format records, stop those writes during migration/cutover. Do not run an automatic legacy ownership mapping. The mapping command remains a separate reviewed operator action.

Record the actual Render HTTPS URL after service creation. A service name is only a request; use the URL Render actually assigns.

## 3. Configure the existing Vercel project

Only switch the existing project to Next.js after the Render backend is reachable and the schema is ready.

| Setting | Value |
| --- | --- |
| Root Directory | frontend |
| Framework Preset | Next.js |
| Node.js | 24.x |
| Install Command | pnpm install --frozen-lockfile |
| Build Command | pnpm build |
| Output Directory | .next |

frontend/vercel.json provides framework/build defaults. Root Directory must still be set in the Vercel dashboard. Remove old Django-specific build/output overrides from that project.

Add the Production environment variable:

DJANGO_API_ORIGIN = the actual https://...onrender.com origin

Do not append /api or a trailing path. Do not use localhost. The frontend configuration now rejects missing or local backend URLs on Vercel, so a bad configuration fails during build rather than leaving a broken login page.

Redeploy after changing this variable; the rewrite target is set at build time. The frontend needs neither DATABASE_URL nor DJANGO_SECRET_KEY. Do not expose secrets with NEXT_PUBLIC_.

For a separate preview environment, use a separate backend/Neon branch and explicitly allow the preview frontend origin. Do not broadly trust all vercel.app projects.

## 4. Verify the complete path

1. Open Render /health/: expect {"status":"ok"}.
2. Open Vercel /api/auth/csrf/: expect JSON, without a redirect loop.
3. Open Vercel /register and register your account.
4. Credit salary, add an expense, and verify the balance.
5. Sign out and verify protected data is unavailable.
6. Verify a second account cannot read the first account's cycles.
7. Confirm old records remain preserved and unassigned until reviewed reconciliation.

Because browser requests stay on the Vercel origin, session cookies belong to that origin. Vercel forwards the cookies to Render. Django validates CSRF against the Vercel HTTPS origin. No cross-site cookie workaround or wildcard CORS configuration is needed.

## Common errors

- Django 400: check the exact backend Host header and ALLOWED_HOSTS.
- Django CSRF 403: confirm the exact frontend HTTPS origin in DJANGO_CSRF_TRUSTED_ORIGINS.
- Build says DJANGO_API_ORIGIN missing: set it in Vercel Production and rebuild.
- API 502/504: verify the Render service is up and its URL is correct; a sleeping free instance can delay the first request.
- Redirect loop: confirm DJANGO_TRUST_PROXY=True on Render, HTTPS forwarding, and the preserved trailing slash in next.config.ts.
- Unapplied migrations at startup: follow the reviewed one-time schema update above.
- New account has no old expenses: legacy records were preserved without guessing ownership; use the reviewed mapping procedure.

## Local verification commands

python manage.py test expense --settings=config.test_settings
python manage.py makemigrations --check --dry-run --settings=config.test_settings

In frontend:
pnpm typecheck
pnpm build

Local checks do not apply migrations to Neon. Gunicorn runs on Render's Linux runtime; Windows development continues to use python manage.py runserver.
