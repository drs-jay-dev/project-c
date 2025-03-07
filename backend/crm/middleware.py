import logging
from datetime import timedelta
from django.utils import timezone
from .models import OAuth2Token
from .ghl_oauth import refresh_token

logger = logging.getLogger(__name__)

class TokenRefreshMiddleware:
    """
    Middleware to automatically refresh tokens that are about to expire
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization
        self.last_check = timezone.now()
        self.check_interval = timedelta(minutes=30)  # Check every 30 minutes

    def __call__(self, request):
        # Check if it's time to refresh tokens
        now = timezone.now()
        if now - self.last_check > self.check_interval:
            self.refresh_expiring_tokens()
            self.last_check = now

        response = self.get_response(request)
        return response
    
    def refresh_expiring_tokens(self):
        """
        Refresh tokens that will expire in the next 6 hours
        """
        logger.info("Checking for tokens that need refreshing")
        expiry_threshold = timezone.now() + timedelta(hours=6)
        
        # Find tokens that will expire in the next 6 hours but haven't expired yet
        expiring_tokens = OAuth2Token.objects.filter(
            expires_at__lt=expiry_threshold,
            expires_at__gt=timezone.now()
        )
        
        count = expiring_tokens.count()
        if count > 0:
            logger.info(f"Found {count} tokens that need refreshing")
            
            for token in expiring_tokens:
                try:
                    logger.info(f"Auto-refreshing token for location {token.location_id}")
                    refresh_token(token)
                    logger.info(f"Successfully refreshed token for location {token.location_id}")
                except Exception as e:
                    logger.error(f"Failed to refresh token for location {token.location_id}: {str(e)}")
        else:
            logger.info("No tokens need refreshing at this time")
