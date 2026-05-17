"""
ASGI config for teachly project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

default_settings = (
    "teachly.settings.production"
    if os.environ.get("VERCEL") == "1"
    else "teachly.settings.development"
)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", default_settings)

application = get_asgi_application()
