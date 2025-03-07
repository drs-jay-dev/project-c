import time
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from crm.models import OAuth2Token, SystemLog, SyncState
from crm.ghl_sync import sync_all_ghl_contacts, sync_updated_ghl_contacts
from crm.utils import log_system_event

class Command(BaseCommand):
    help = 'Sync contacts from GoHighLevel'

    def add_arguments(self, parser):
        parser.add_argument('--location-id', type=str, help='GoHighLevel location ID')
        parser.add_argument('--page-limit', type=int, default=100, help='Number of contacts per page')
        parser.add_argument('--start-page', type=int, default=1, help='Page to start syncing from')
        parser.add_argument('--max-pages', type=int, help='Maximum number of pages to process')
        parser.add_argument('--no-progress', action='store_true', help='Disable progress tracking')
        parser.add_argument('--modified-after', type=str, help='Only sync contacts modified after this date (YYYY-MM-DD)')
        parser.add_argument('--chunk-size', type=int, default=10, 
                            help='Number of pages to process in each chunk (for chunked sync)')
        parser.add_argument('--chunk-delay', type=int, default=60,
                            help='Delay in seconds between chunks')
        parser.add_argument('--chunked', action='store_true', 
                            help='Run sync in chunks with delays between them')
        parser.add_argument('--incremental', action='store_true',
                            help='Only sync contacts modified since last sync')
        parser.add_argument('--resume', action='store_true',
                            help='Resume from last interrupted sync')

    def handle(self, *args, **options):
        location_id = options['location_id']
        
        # If no location ID provided, use the first available token
        if not location_id:
            token = OAuth2Token.objects.first()
            if not token:
                raise CommandError('No OAuth tokens found. Please authenticate with GoHighLevel first.')
            location_id = token.location_id
            self.stdout.write(f"Using location ID: {location_id}")
        
        page_limit = options['page_limit']
        start_page = options['start_page']
        max_pages = options['max_pages']
        track_progress = not options['no_progress']
        
        # Check if we should resume from a previous sync
        if options['resume']:
            sync_state = SyncState.objects.filter(
                sync_type='ghl_contacts',
                location_id=location_id,
                is_complete=False
            ).first()
            
            if sync_state:
                start_page = sync_state.last_page_processed + 1
                self.stdout.write(f"Resuming sync from page {start_page}")
            else:
                self.stdout.write("No incomplete sync found to resume")
        
        # Parse modified_after date if provided
        modified_after = None
        if options['modified_after']:
            try:
                modified_after = datetime.strptime(options['modified_after'], '%Y-%m-%d')
                modified_after = timezone.make_aware(modified_after)
                self.stdout.write(f"Syncing contacts modified after {modified_after}")
            except ValueError:
                raise CommandError('Invalid date format. Please use YYYY-MM-DD.')
        
        # If incremental sync is requested
        if options['incremental']:
            self.stdout.write("Starting incremental sync")
            success, errors, last_page = sync_updated_ghl_contacts(location_id)
            self.stdout.write(self.style.SUCCESS(
                f"Incremental sync completed: {success} contacts synced, {errors} errors. Last page: {last_page}"
            ))
            return
        
        # Create or update sync state
        sync_state, created = SyncState.objects.update_or_create(
            sync_type='ghl_contacts',
            location_id=location_id,
            defaults={
                'last_sync_time': timezone.now(),
                'is_complete': False
            }
        )
        
        try:
            # If chunked sync is requested
            if options['chunked']:
                chunk_size = options['chunk_size']
                chunk_delay = options['chunk_delay']
                
                self.stdout.write(f"Starting chunked sync with {chunk_size} pages per chunk")
                
                current_page = start_page
                total_success = 0
                total_errors = 0
                
                while True:
                    self.stdout.write(f"Processing chunk starting at page {current_page}")
                    
                    # Process a chunk of pages
                    success, errors, last_page = sync_all_ghl_contacts(
                        location_id=location_id,
                        page_limit=page_limit,
                        start_page=current_page,
                        max_pages=chunk_size,
                        track_progress=track_progress,
                        sync_modified_after=modified_after
                    )
                    
                    total_success += success
                    total_errors += errors
                    
                    # Update sync state
                    sync_state.last_page_processed = last_page
                    sync_state.success_count = total_success
                    sync_state.error_count = total_errors
                    sync_state.save()
                    
                    self.stdout.write(self.style.SUCCESS(
                        f"Chunk completed: {success} contacts synced, {errors} errors. Last page: {last_page}"
                    ))
                    
                    # If we've reached the end or hit max_pages
                    if last_page < current_page + chunk_size - 1 or (max_pages and last_page >= start_page + max_pages - 1):
                        break
                    
                    # Update current page for next chunk
                    current_page = last_page + 1
                    
                    # Wait between chunks
                    self.stdout.write(f"Waiting {chunk_delay} seconds before next chunk...")
                    time.sleep(chunk_delay)
                
                self.stdout.write(self.style.SUCCESS(
                    f"Chunked sync completed: {total_success} contacts synced, {total_errors} errors"
                ))
                
                # Mark sync as complete
                sync_state.is_complete = True
                sync_state.total_pages = last_page
                sync_state.save()
                
            else:
                # Regular sync
                self.stdout.write(f"Starting sync from page {start_page}")
                
                success, errors, last_page = sync_all_ghl_contacts(
                    location_id=location_id,
                    page_limit=page_limit,
                    start_page=start_page,
                    max_pages=max_pages,
                    track_progress=track_progress,
                    sync_modified_after=modified_after
                )
                
                # Update sync state
                sync_state.last_page_processed = last_page
                sync_state.success_count = success
                sync_state.error_count = errors
                sync_state.is_complete = True
                sync_state.total_pages = last_page
                sync_state.save()
                
                self.stdout.write(self.style.SUCCESS(
                    f"Sync completed: {success} contacts synced, {errors} errors. Last page: {last_page}"
                ))
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Sync interrupted by user"))
            log_system_event(
                "Sync interrupted by user",
                type='sync',
                status='warning',
                details={
                    'sync_type': 'ghl_contacts',
                    'location_id': location_id,
                    'last_page_processed': sync_state.last_page_processed
                }
            )
            return
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during sync: {str(e)}"))
            log_system_event(
                f"Error during sync: {str(e)}",
                type='sync',
                status='error',
                details={
                    'sync_type': 'ghl_contacts',
                    'location_id': location_id,
                    'last_page_processed': sync_state.last_page_processed
                }
            )
            raise
