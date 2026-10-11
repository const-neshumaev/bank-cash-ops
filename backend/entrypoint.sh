#!/bin/sh
# Container entrypoint: prepare the database and the initial administrator
# before handing control over to the container command.
set -e

echo ">> Applying database migrations"
python manage.py migrate --noinput

echo ">> Creating the initial administrator (if configured)"
python manage.py ensure_superuser

if [ "${DJANGO_COLLECTSTATIC:-0}" = "1" ]; then
    echo ">> Collecting static files"
    python manage.py collectstatic --noinput
fi

exec "$@"
