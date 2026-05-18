import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'

    def ready(self):
        # Hosted previews (e.g. Vercel) may ship without running management commands.
        if os.environ.get('VERCEL') != '1':
            return
        try:
            from dashboard.demo_accounts import ensure_minimal_demo_accounts

            ensure_minimal_demo_accounts()
        except Exception:
            logger.exception('Minimal demo account bootstrap failed')