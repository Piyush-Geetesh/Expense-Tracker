# Expense Tracker

Django 5.2 + Django REST Framework own authentication, ownership, money validation, and salary-cycle rules. Next.js provides the interface at the public origin; its /api/ requests are forwarded to Django.

## Run locally

Use Python 3.10+ and Node.js 20.9+ (Node 24 was used for validation). The older Node 14 installation on this machine cannot run this frontend.

1. Install the backend dependencies: `python -m pip install -r requirements.txt`.
2. Set environment variables using [.env.example](.env.example) as a reference. Django now loads the root .env file for local use; existing environment variables take precedence. Render uses its dashboard environment variables.
3. **Before migrating any database containing real data, follow [docs/MIGRATION.md](docs/MIGRATION.md).** On a new, empty development database, run `python manage.py migrate`.
4. Start Django: `python manage.py runserver 127.0.0.1:8000`.
5. In `frontend/`, install dependencies with `pnpm install --frozen-lockfile`. Set `DJANGO_API_ORIGIN=http://127.0.0.1:8000` if needed (this is the default).
6. Run `pnpm dev` and open http://localhost:3000. Register a new account.

Use the frontend origin for all browser requests. There is no token in local storage. The session cookie is HttpOnly; unsafe requests send a CSRF token. Login and registration enforce CSRF even for anonymous requests.

## Behavior

- Credit a positive salary to start the current cycle.
- Expenses are assigned by Django to that user's active cycle and cannot exceed its balance.
- At exactly zero, the cycle completes and a new salary is allowed.
- Balance = that cycle's salary minus that cycle's expenses; no duplicate balance is stored.
- Descriptions are preserved exactly. Text before the first hyphen, with whitespace cleaned and title capitalization, becomes the stored category. No prefix means Other.
- Individual deletion removes only the owned expense. Delete-all removes only the selected owned cycle's expenses.
- Deleting from the latest cycle restores its balance and reopens it. After a newer cycle exists, older cycles stay historical even if deletions restore a positive balance. A zero-balance older cycle is displayed as completed.
- Unassigned legacy data is preserved but inaccessible through user APIs. Accounts do not automatically claim legacy records.
- The previous template route returns 410 and its unrestricted deletion route is removed.

## Verification

Backend tests always use a disposable database with this command:

```text
python manage.py test expense --settings=config.test_settings
python manage.py makemigrations --check --dry-run --settings=config.test_settings
```

Frontend checks, from `frontend/`:

```text
pnpm typecheck
pnpm build
```

Browser tests require Microsoft Edge (the Playwright configuration uses its installed browser). Prepare the separate local test database, then run the tests:

```text
python manage.py migrate --settings=config.e2e_settings --noinput
cd frontend
pnpm test:e2e
```

The tests start Django on port 8001 and Next.js on port 3001 and stop them afterwards. Test accounts use unique names. Only `e2e.sqlite3` receives browser-test data; the existing `db.sqlite3` is not used. Screenshots and failure traces go to `frontend/test-results/`. Never use test/e2e settings to serve real users.

## API

All financial endpoints require a Django session and filter records by the authenticated user. Foreign and nonexistent IDs both return 404. Submitted ownership/cycle/category fields are rejected. Money is serialized as decimal strings.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /api/auth/csrf/ | Public CSRF initialization |
| POST | /api/auth/register/ | username/password; register and sign in |
| POST | /api/auth/login/ | username/password; sign in |
| POST | /api/auth/logout/ | Invalidate session |
| GET | /api/auth/me/ | Current username |
| GET | /api/dashboard/ | Current cycle, recent expenses, allowed actions |
| GET / POST | /api/cycles/ | Paginated history / credit salary with amount |
| GET | /api/cycles/{id}/ | Cycle totals, status, category summary |
| GET | /api/cycles/{id}/expenses/ | Paginated expenses |
| POST | /api/expenses/ | amount and original description |
| DELETE | /api/expenses/{id}/ | Delete one owned expense |
| DELETE | /api/cycles/{id}/expenses/ | Delete this cycle's expenses, retain cycle |

List pages contain count, next, previous, and results; request `?page=2` to advance. Errors return JSON with detail or field messages. Validation is 400, missing/foreign records 404, unauthenticated/CSRF failures 403, and temporary database failures 503. The browser displays failures and does not automatically retry financial writes.

## Render backend + Vercel frontend

Follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the exact Render, Neon, and Vercel settings. The Render blueprint uses your existing Neon database and does not create a replacement database.

## Production configuration

This change does not deploy anything or migrate your production database.

- Set DEBUG=False, a strong DJANGO_SECRET_KEY, explicit DJANGO_ALLOWED_HOSTS, and DJANGO_CSRF_TRUSTED_ORIGINS to the actual HTTPS frontend origin.
- Serve both UI and /api/ on one public HTTPS origin. Set DJANGO_API_ORIGIN before building Next.js; external rewrites are included in the build configuration.
- Forward cookies and Set-Cookie through the proxy; never cache /api/ responses. Django returns Cache-Control: no-store, private.
- Configure HTTPS termination correctly. Set DJANGO_TRUST_PROXY=True only when the trusted proxy strips user-supplied X-Forwarded-Proto and supplies it itself. Otherwise keep it false and serve Django over HTTPS.
- Secure cookies, SSL redirect, and HSTS are enabled with DEBUG=False. No permissive CORS middleware is installed because the browser uses one origin.
- Use PostgreSQL through DATABASE_URL for multi-worker production. Transactions lock the user row before finding a cycle or reading its balance, including the first-salary race.
- SQLite development writes acquire a database write lock before balance reads. A lock timeout fails the whole operation. It is safe against overdrafts but has lower write concurrency.
- Before a PostgreSQL rollout, run the test suite against a dedicated disposable PostgreSQL test database as well; the local verified suite uses SQLite.
- Login/registration have basic anonymous throttling. At a multi-worker public deployment, enforce authentication rate limits at the trusted reverse proxy or use a shared Django cache; the default local-memory throttle is per process.
- Use your normal production WSGI/ASGI process manager for Django and `pnpm build && pnpm start` for Next.js. Django's development server is for local use only.

Existing settings still support DATABASE_URL. No account deletion, salary editing, notifications, or automatic ownership guessing is added.
