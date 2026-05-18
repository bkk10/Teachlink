"""
Middleware to store JWT token in session for template access
"""
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)


class TokenMiddleware(MiddlewareMixin):
    """
    Store JWT token from Authorization header in session
    for use in templates
    """
    
    def process_request(self, request):
        """
        Extract token from Authorization header and store in session
        """
        if not hasattr(request, "user"):
            return

        try:
            if not request.user.is_authenticated:
                return
            # For session-based auth, set a simple token for templates.
            request.session["auth_token"] = "session-authenticated"
            request.auth_token = "session-authenticated"
        except Exception as exc:
            # Avoid taking down public pages if auth/session backend is unavailable.
            logger.warning("TokenMiddleware skipped due to auth/session error: %s", exc)
            return
