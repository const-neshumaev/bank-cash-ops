"""
Django settings for the BankCashOps project.

Every deployment specific value is read from environment variables, so the very
same code base can run locally, inside Docker and in production without edits.
"""

import sys
from datetime import timedelta
from pathlib import Path

import environ
from django.utils.translation import gettext_lazy as _

# Directory that contains ``manage.py``.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173", "http://127.0.0.1:5173"]),
    CSRF_TRUSTED_ORIGINS=(list, ["http://localhost:5173", "http://127.0.0.1:5173"]),
    DJANGO_TIME_ZONE=(str, "Europe/Moscow"),
)

# Load a local .env file when present (convenient for running without Docker).
_env_file = BASE_DIR.parent / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-development-key-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# True while the automated test suite runs; used to skip production-only wiring.
TESTING = "pytest" in sys.modules or "test" in sys.argv


# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # Local modules
    "modules.common.backend",
    "modules.core.backend",
    "modules.operations.backend",
    "modules.operations_standard.backend",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
]

# WhiteNoise serves the collected static files in production. It is skipped in
# development (runserver serves static itself) and during the test suite.
if not DEBUG and not TESTING:
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")

MIDDLEWARE += [
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Activates the request language from ``Accept-Language`` (see the
    # internationalisation block below and ADR 0015). It must sit after the
    # session middleware and before ``CommonMiddleware``.
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
# PostgreSQL is the only database, used by development, tests and production
# alike. The connection is configured exclusively through DATABASE_URL; there is
# no fallback engine, so a misconfigured environment fails loudly instead of
# silently running on an incompatible database. Each module owns its own schema
# (see docs/adr/0013-postgresql-schemas-per-module.md).
DATABASES = {"default": env.db_url("DATABASE_URL")}
DATABASES["default"].setdefault("CONN_MAX_AGE", 60)


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #
AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --------------------------------------------------------------------------- #
# Internationalisation
# --------------------------------------------------------------------------- #
# The application is multilingual (docs/adr/0015-application-language-layers.md):
# every response is rendered in the language of the request (``Accept-Language``,
# activated by ``LocaleMiddleware``), the per-user choice lives in ``core.User``
# and the bank-wide default below is the fallback when neither is present.
LANGUAGE_CODE = env("BCO_DEFAULT_LANGUAGE", default="ru")
# Languages the application offers. Adding one means adding an entry here and the
# matching translation catalogs (``locale/<lang>/LC_MESSAGES``).
LANGUAGES = [
    ("ru", _("Russian")),
    ("en", _("English")),
]
# Translation catalogs live inside each module (``modules/<name>/backend/locale``)
# and Django discovers them automatically as app-level locale directories. There is
# deliberately no ``LOCALE_PATHS``: ``makemessages`` then writes into the catalog of
# the module it is run in, instead of a shared host directory.
TIME_ZONE = env("DJANGO_TIME_ZONE")
USE_I18N = True
USE_TZ = True


# --------------------------------------------------------------------------- #
# Static files
# --------------------------------------------------------------------------- #
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

if DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

WHITENOISE_USE_FINDERS = DEBUG

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------------------------------- #
# Cross-origin requests
# --------------------------------------------------------------------------- #
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")


# --------------------------------------------------------------------------- #
# Django REST Framework
# --------------------------------------------------------------------------- #
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "modules.common.backend.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {"login": env("LOGIN_THROTTLE_RATE", default="20/min")},
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=60)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "BankCashOps API",
    "DESCRIPTION": "REST API of the Bank Cash Operation System.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
