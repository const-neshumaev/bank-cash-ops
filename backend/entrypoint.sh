#!/bin/sh
# Container entrypoint: prepare the database and the initial administrator
# before handing control over to the container command.
set -e

echo ">> Applying database migrations"
python manage.py migrate --noinput

# The development image ships gettext and compiles the catalogs of the mounted
# sources at every start; the production image has them baked at build time and
# no ``msgfmt``, so the step is skipped there.
if command -v msgfmt > /dev/null 2>&1; then
    echo ">> Compiling translation catalogs"
    python manage.py compilemessages
fi

echo ">> Creating the initial administrator (if configured)"
python manage.py ensure_superuser

echo ">> Syncing the declared print templates"
python manage.py sync_print_templates

echo ">> Syncing the declared operation types"
python manage.py sync_operation_types

if [ "${DJANGO_COLLECTSTATIC:-0}" = "1" ]; then
    echo ">> Collecting static files"
    python manage.py collectstatic --noinput
fi

exec "$@"
