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
        print(f"TokenMiddleware processing request for {request.path}")
        print(f"   User authenticated: {request.user.is_authenticated}")
        
        # Skip for non-authenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return
        
        # For session-based auth, just set a simple token
        request.session['auth_token'] = 'session-authenticated'
        request.auth_token = 'session-authenticated'
        print(f"   Set session token for {request.user.email}")
