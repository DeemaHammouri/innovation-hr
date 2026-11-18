#!/bin/sh
# Render free-plan start-up for the API: migrate, create the first accounts, then serve.
# (No Shell on the free plan, so the accounts are created here. Both steps are safe to repeat.)
set -e
python manage.py migrate --noinput

if [ -n "$CEO_EMAIL" ] && [ -n "$CEO_PASSWORD" ]; then
  python manage.py seed || echo "seed failed (continuing)"
else
  echo "CEO_EMAIL/CEO_PASSWORD not set: skipping seed"
fi

if [ -n "$ADMIN_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py createsuperuser --noinput --email "$ADMIN_EMAIL" --full_name "${ADMIN_NAME:-System Admin}" || echo "createsuperuser skipped (already exists?)"
else
  echo "ADMIN_EMAIL/DJANGO_SUPERUSER_PASSWORD not set: skipping createsuperuser"
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile -
