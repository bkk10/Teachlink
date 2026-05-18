from .base import *
import os
from importlib.util import find_spec

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']
vercel_url = os.getenv("VERCEL_URL", "").strip()
if vercel_url and vercel_url not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(vercel_url)
if ".vercel.app" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".vercel.app")

# Use SQLite for initial development (switch to PostgreSQL later)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Disable password validation in dev
AUTH_PASSWORD_VALIDATORS = []

# Email backend for development:
# inherits from base.py and can be overridden using environment variables.

# Development-specific apps
if find_spec("django_extensions") is not None:
    INSTALLED_APPS += [
        "django_extensions",
    ]

REST_FRAMEWORK = {
    # ... your existing DRF settings
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Teachly API',
    'DESCRIPTION': 'Teachly API Documentation',
    'VERSION': '1.0.0',
}

# Logging for debugging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
