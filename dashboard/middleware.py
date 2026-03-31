"""
Middleware to store JWT token in session for template access
"""
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class TokenMiddleware(MiddlewareMixin):
    """
    Store JWT token from Authorization header in session
    for use in templates
    
    This middleware extracts the JWT token from the Authorization header
    and stores it in the session so it can be accessed in templates
    for AJAX requests that need authentication.
    """
    
    def process_request(self, request):
        """
        Extract token from Authorization header and store in session
        """
        # Skip for non-authenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return
        
        # Check Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if auth_header.startswith('Bearer '):
            # Extract token (remove 'Bearer ' prefix)
            token = auth_header[7:]
            
            # Store in session
            request.session['auth_token'] = token
            
            # Also store in request for easy access
            request.auth_token = token
            
        elif settings.DEBUG and not request.session.get('auth_token'):
            # In development, you might want a placeholder
            # NEVER do this in production!
            logger.warning("No auth token found in request - using session token if available")
            
            # Only use existing session token if present
            if request.session.get('auth_token'):
                request.auth_token = request.session.get('auth_token')
    
    def process_response(self, request, response):
        """
        Clean up any sensitive data if needed
        """
        # Optionally remove token from session for security
        # But we need it for templates, so we keep it
        return response