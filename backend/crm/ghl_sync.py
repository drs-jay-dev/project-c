import requests
import json
import logging
import time
import uuid
from django.utils import timezone
from .models import Contact, OAuth2Token
from .ghl_oauth import get_valid_token
from .utils import log_system_event

logger = logging.getLogger(__name__)

def get_ghl_headers(token):
    """
    Get headers for GoHighLevel API requests
    """
    return {
        'Authorization': f'Bearer {token.access_token}',
        'Version': '2021-07-28',
        'Content-Type': 'application/json'
    }

def search_ghl_contacts(location_id, search_params=None, page=1, page_limit=100):
    """
    Search for contacts in GoHighLevel
    
    Args:
        location_id (str): The GoHighLevel location ID
        search_params (dict): Optional search parameters
        page (int): Page number (starting at 1)
        page_limit (int): Number of results per page
        
    Returns:
        dict: The API response
    """
    token = get_valid_token(location_id)
    if not token:
        logger.error(f"No valid token found for location {location_id}")
        return None
    
    url = "https://services.leadconnectorhq.com/contacts/search"
    headers = get_ghl_headers(token)
    
    payload = {
        "locationId": location_id,
        "page": page,
        "pageLimit": page_limit
    }
    
    if search_params:
        payload.update(search_params)
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error searching GHL contacts: {str(e)}")
        return None

def get_ghl_contact(location_id, contact_id):
    """
    Get a single contact from GoHighLevel by ID
    
    Args:
        location_id (str): The GoHighLevel location ID
        contact_id (str): The GoHighLevel contact ID
        
    Returns:
        dict: The contact data
    """
    token = get_valid_token(location_id)
    if not token:
        logger.error(f"No valid token found for location {location_id}")
        return None
    
    url = f"https://services.leadconnectorhq.com/contacts/{contact_id}"
    headers = get_ghl_headers(token)
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting GHL contact: {str(e)}")
        return None

def sync_ghl_contact(location_id, ghl_contact_data):
    """
    Sync a GoHighLevel contact to the local database
    
    Args:
        location_id (str): The GoHighLevel location ID
        ghl_contact_data (dict): The contact data from GoHighLevel
        
    Returns:
        Contact: The created or updated Contact object
    """
    try:
        ghl_id = ghl_contact_data.get('id')
        if not ghl_id:
            logger.error("Contact data missing ID")
            return None
        
        # Try to find an existing contact by GHL ID
        contact = Contact.objects.filter(ghl_contact_id=ghl_id).first()
        
        # If not found by GHL ID, try by phone or email
        if not contact:
            phone = ghl_contact_data.get('phone')
            email = ghl_contact_data.get('email')
            
            if phone:
                contact = Contact.objects.filter(phone=phone).first()
            
            if not contact and email:
                contact = Contact.objects.filter(email=email).first()
        
        # Extract contact data
        contact_data = {
            'first_name': ghl_contact_data.get('firstName', ''),
            'last_name': ghl_contact_data.get('lastName', ''),
            'phone': ghl_contact_data.get('phone') or '',  # Use empty string if phone is None
            'normalized_phone': ghl_contact_data.get('phone') or '',  # Also set normalized_phone
            'ghl_contact_id': ghl_id,
            'ghl_data': ghl_contact_data,
            'ghl_last_sync': timezone.now(),
        }
        
        # Print contact data for debugging
        print(f"Contact data: {contact_data}")
        
        # Only add email if it exists
        if ghl_contact_data.get('email'):
            contact_data['email'] = ghl_contact_data.get('email')
        
        # Extract GHL tags if present
        if 'tags' in ghl_contact_data:
            contact_data['ghl_tags'] = ghl_contact_data.get('tags', [])
        
        # Extract custom fields if present
        if 'customFields' in ghl_contact_data:
            contact_data['ghl_custom_fields'] = ghl_contact_data.get('customFields', [])
        
        # If we found an existing contact, update it
        if contact:
            # Set primary source to GHL if it was previously CRM only
            if contact.primary_source == 'crm':
                contact_data['primary_source'] = 'ghl'
                
            # Update the contact with the new data
            for key, value in contact_data.items():
                setattr(contact, key, value)
            contact.save()
            logger.info(f"Updated contact: {contact}")
        else:
            # Create a new contact
            contact_data['primary_source'] = 'ghl'
            try:
                contact = Contact.objects.create(**contact_data)
                logger.info(f"Created new contact: {contact}")
            except Exception as create_error:
                print(f"Error creating contact: {str(create_error)}")
                print(f"Contact data: {contact_data}")
                raise
        
        return contact
    except Exception as e:
        import traceback
        logger.error(f"Error syncing contact: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        print(f"Error syncing contact: {str(e)}")
        print(f"Full traceback: {traceback.format_exc()}")
        print(f"Contact data: {ghl_contact_data}")
        return None

def sync_all_ghl_contacts(location_id, page_limit=100, start_page=1, max_pages=None, 
                          track_progress=True, sync_modified_after=None):
    """
    Sync all contacts from GoHighLevel to the local database
    
    Args:
        location_id (str): The GoHighLevel location ID
        page_limit (int): Number of results per page
        start_page (int): Page to start syncing from (for resuming interrupted syncs)
        max_pages (int): Maximum number of pages to process (None for all pages)
        track_progress (bool): Whether to create system logs for tracking progress
        sync_modified_after (datetime): Only sync contacts modified after this date
        
    Returns:
        tuple: (success_count, error_count, last_page_processed)
    """
    page = start_page
    has_more = True
    success_count = 0
    error_count = 0
    
    # Create a sync session log
    if track_progress:
        sync_id = str(uuid.uuid4())
        log_system_event(
            f"Starting GHL contact sync session {sync_id} from page {start_page}",
            type='sync',
            status='in_progress',
            details={
                'sync_id': sync_id,
                'location_id': location_id,
                'start_page': start_page,
                'max_pages': max_pages,
                'sync_modified_after': sync_modified_after.isoformat() if sync_modified_after else None
            }
        )
    
    # Prepare search params for incremental sync if needed
    search_params = {}
    if sync_modified_after:
        search_params['filters'] = [{
            'field': 'dateUpdated',
            'operator': 'greater_than',
            'value': sync_modified_after.isoformat()
        }]
        
        # Sort by update date to get newest first
        search_params['sort'] = [{
            'field': 'dateUpdated',
            'direction': 'desc'
        }]
    
    try:
        while has_more:
            if max_pages and (page - start_page + 1) > max_pages:
                logger.info(f"Reached maximum page limit of {max_pages}")
                break
                
            if track_progress and page % 5 == 0:  # Log progress every 5 pages
                log_system_event(
                    f"Syncing GHL contacts - processing page {page}",
                    type='sync',
                    status='in_progress',
                    details={
                        'sync_id': sync_id if track_progress else None,
                        'page': page,
                        'success_count': success_count,
                        'error_count': error_count
                    }
                )
                
            logger.info(f"Fetching GHL contacts page {page}")
            result = search_ghl_contacts(location_id, search_params=search_params, 
                                        page=page, page_limit=page_limit)
            
            if not result or 'contacts' not in result:
                error_msg = f"Failed to get contacts for page {page}"
                logger.error(error_msg)
                error_count += 1
                
                if track_progress:
                    log_system_event(
                        error_msg,
                        type='sync',
                        status='error',
                        details={
                            'sync_id': sync_id,
                            'page': page,
                            'response': result
                        }
                    )
                
                # Wait before retrying to avoid hitting rate limits
                time.sleep(5)
                
                # Try up to 3 times before giving up on this page
                retry_count = 0
                while retry_count < 3 and (not result or 'contacts' not in result):
                    retry_count += 1
                    logger.info(f"Retrying page {page} (attempt {retry_count}/3)")
                    time.sleep(5 * retry_count)  # Exponential backoff
                    result = search_ghl_contacts(location_id, search_params=search_params, 
                                               page=page, page_limit=page_limit)
                
                if not result or 'contacts' not in result:
                    logger.error(f"Giving up on page {page} after 3 retries")
                    break
            
            contacts = result.get('contacts', [])
            
            if not contacts:
                logger.info(f"No contacts found on page {page}")
                has_more = False
                continue
            
            logger.info(f"Processing {len(contacts)} contacts from page {page}")
            
            # Process contacts in smaller batches to avoid memory issues
            batch_size = 20
            for i in range(0, len(contacts), batch_size):
                batch = contacts[i:i+batch_size]
                for contact_data in batch:
                    try:
                        sync_ghl_contact(location_id, contact_data)
                        success_count += 1
                    except Exception as e:
                        logger.exception(f"Error syncing contact: {str(e)}")
                        error_count += 1
                
                # Small pause between batches to reduce database load
                time.sleep(0.5)
            
            # Check if there are more pages
            total_count = result.get('total', 0)
            current_count = page * page_limit
            has_more = current_count < total_count
            
            # Save the last processed page in case we need to resume
            last_page_processed = page
            page += 1
            
            # Add a small delay between pages to avoid hitting rate limits
            time.sleep(2)
    
    except Exception as e:
        logger.exception(f"Unexpected error during GHL contact sync: {str(e)}")
        if track_progress:
            log_system_event(
                f"Sync interrupted: {str(e)}",
                type='sync',
                status='error',
                details={
                    'sync_id': sync_id,
                    'last_page_processed': page - 1,
                    'success_count': success_count,
                    'error_count': error_count
                }
            )
        return success_count, error_count, page - 1
    
    # Log completion
    if track_progress:
        log_system_event(
            f"Completed GHL contact sync session {sync_id}",
            type='sync',
            status='success',
            details={
                'sync_id': sync_id,
                'total_pages': page - 1,
                'success_count': success_count,
                'error_count': error_count
            }
        )
    
    return success_count, error_count, page - 1

def sync_updated_ghl_contacts(location_id):
    """
    Sync only contacts that have been updated since the last sync
    
    Args:
        location_id (str): The GoHighLevel location ID
        
    Returns:
        tuple: (success_count, error_count, last_page_processed)
    """
    # Find the last sync time for this location
    last_sync = Contact.objects.filter(
        ghl_location_id=location_id,
        ghl_last_sync__isnull=False
    ).order_by('-ghl_last_sync').first()
    
    if not last_sync or not last_sync.ghl_last_sync:
        # If no previous sync, do a full sync
        logger.info(f"No previous sync found for location {location_id}, performing full sync")
        return sync_all_ghl_contacts(location_id)
    
    # Get contacts updated since last sync
    sync_modified_after = last_sync.ghl_last_sync
    logger.info(f"Performing incremental sync for contacts updated since {sync_modified_after}")
    
    return sync_all_ghl_contacts(
        location_id=location_id,
        sync_modified_after=sync_modified_after
    )
