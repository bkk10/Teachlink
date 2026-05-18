from .base import *
import os
from dotenv import load_dotenv

load_dotenv()

DEBUG = False

def _csv_env(key):
    return [v.strip() for v in os.getenv(key, "").split(",") if v.strip()]


# Prefer explicit hosts from env; add Render hostname fallback to avoid DisallowedHost.
ALLOWED_HOSTS = _csv_env("ALLOWED_HOSTS")
vercel_url = os.getenv("VERCEL_URL", "").strip()
if vercel_url and vercel_url not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(vercel_url)
if ".vercel.app" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".vercel.app")
render_external_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
if render_external_hostname and render_external_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_external_hostname)
if ".onrender.com" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".onrender.com")

# PostgreSQL for production if env vars provided, otherwise fall back to SQLite
if os.getenv('DB_NAME') and os.getenv('DB_USER') and os.getenv('DB_PASSWORD'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    # Useful for quick deploys/tests when an external Postgres isn't configured
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    # Serverless-safe fallback: avoid DB-backed session writes on ephemeral/readonly SQLite.
    SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True

# Static files
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

