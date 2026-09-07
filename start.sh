#!/usr/bin/env bash
set -euo pipefail
# Explicit opt-in only after backing up Neon and reviewing the migration plan.
if [ "${RUN_MIGRATIONS:-False}" = "True" ]; then
  python manage.py migrate --noinput
fi
# Fail clearly instead of serving an application with an outdated schema.
python manage.py migrate --check
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" \
  --workers "${WEB_CONCURRENCY:-2}" --access-logfile - --error-logfile -
