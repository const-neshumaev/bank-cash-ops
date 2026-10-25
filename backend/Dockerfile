# Development image for the BankCashOps backend.
# Build context is the repository root so the image can include both the Django
# host project (backend/) and the vertical modules (modules/).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install the dependencies with a current pip. pip is not kept in the final image
# (see below), so this only makes the build use an up-to-date resolver.
RUN pip install --upgrade "pip~=26.2"

# ``gettext`` provides ``msgfmt``/``xgettext`` for ``compilemessages``/
# ``makemessages`` (see the internationalisation section of docs/development.md).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY backend/ ./
COPY modules/ /app/modules/

RUN chmod +x /app/entrypoint.sh

# Dependencies are baked into the image and installed by rebuilding it, so pip is
# not needed at runtime. Dropping it also drops the outdated libraries it vendors
# (msgpack, setuptools, urllib3), which scanners report as vulnerable.
RUN python -m pip uninstall -y pip

EXPOSE 8000

# Run the entrypoint through sh and strip carriage returns first: a file checked
# out on Windows may carry CRLF, which breaks a POSIX shell script.
ENTRYPOINT ["sh", "-c", "tr -d '\\r' < /app/entrypoint.sh > /tmp/entrypoint.sh && exec sh /tmp/entrypoint.sh \"$@\"", "--"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
