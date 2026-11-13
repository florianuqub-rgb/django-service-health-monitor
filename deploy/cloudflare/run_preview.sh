#!/bin/sh
set -eu

: "${DJANGO_SECRET_KEY:?Set DJANGO_SECRET_KEY}"
: "${SERVICE_TOKEN_KEY:?Set SERVICE_TOKEN_KEY}"
: "${PREVIEW_ADMIN_PASSWORD:?Set PREVIEW_ADMIN_PASSWORD}"

redis-server --port 6379 --save '' --appendonly no --daemonize yes
python manage.py migrate --noinput
python - <<'PY'
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model

username = os.getenv("PREVIEW_ADMIN_USERNAME", "previewadmin")
user, _ = get_user_model().objects.get_or_create(username=username)
user.is_staff = True
user.is_superuser = True
user.set_password(os.environ["PREVIEW_ADMIN_PASSWORD"])
user.save()
PY

python manage.py seed_demo

python -m celery -A config worker --pool=solo -l WARNING &
python -m celery -A config beat -l WARNING &
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 1 --threads 4 --timeout 60 --access-logfile -
