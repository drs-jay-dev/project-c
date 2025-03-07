import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from crm.models import OAuth2Token
from crm.ghl_oauth import refresh_token

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Refresh GoHighLevel OAuth tokens that are about to expire'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=6,
            help='Refresh tokens that will expire within this many hours'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        self.stdout.write(f"Checking for tokens that will expire in the next {hours} hours...")
        
        expiry_threshold = timezone.now() + timedelta(hours=hours)
        
        # Find tokens that will expire within the specified time but haven't expired yet
        expiring_tokens = OAuth2Token.objects.filter(
            expires_at__lt=expiry_threshold,
            expires_at__gt=timezone.now()
        )
        
        count = expiring_tokens.count()
        if count > 0:
            self.stdout.write(f"Found {count} tokens that need refreshing")
            
            for token in expiring_tokens:
                try:
                    self.stdout.write(f"Refreshing token for location {token.location_id}")
                    old_expires_at = token.expires_at
                    
                    refreshed_token = refresh_token(token)
                    
                    self.stdout.write(self.style.SUCCESS(
                        f"Successfully refreshed token for location {token.location_id}. "
                        f"New expiry: {refreshed_token.expires_at} "
                        f"(was: {old_expires_at})"
                    ))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"Failed to refresh token for location {token.location_id}: {str(e)}"
                    ))
        else:
            self.stdout.write("No tokens need refreshing at this time")
