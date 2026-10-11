from django.db import connection
from django.http import JsonResponse


def health_check(request):
    """Lightweight readiness probe used by Docker and monitoring tools."""

    database_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:  # pragma: no cover - the probe intentionally swallows errors
        database_ok = False

    payload = {"status": "ok" if database_ok else "error", "database": database_ok}
    return JsonResponse(payload, status=200 if database_ok else 503)
