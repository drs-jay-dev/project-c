import os
import json
import logging
import requests
import uuid
from datetime import datetime, timedelta
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from .models import OAuth2Token, TokenRequestLog
from .utils import log_system_event

logger = logging.getLogger(__name__)

def get_token_url():
    return "https://services.leadconnectorhq.com/oauth/token"

def oauth_callback(request):
    """
    Handle the OAuth2 callback from GoHighLevel
    """
    code = request.GET.get('code')
    location_id = request.GET.get('locationId')
    state = request.GET.get('state')
    
    logger.info(f"OAuth callback received with params: {request.GET}")
    
    if not code:
        error = "Missing required parameter: code"
        logger.error(f"OAuth callback error: {error}")
        return JsonResponse({"error": error}, status=400)
    
    # If locationId is not provided in the callback URL, we need to handle this case
    if not location_id:
        # Check if we have a location ID stored in the session
        location_id = request.session.get('ghl_location_id')
        
        if not location_id:
            # If we still don't have a location ID, use a default one for now
            # In a production environment, you would want to ask the user to select a location
            logger.warning("No locationId provided in callback or session, using default")
            location_id = 'pgfekl6sKgofVPSuYOJo'  # Default location ID
    
    # Exchange the authorization code for an access token
    token_url = get_token_url()
    oauth_settings = settings.GOHIGHLEVEL_OAUTH
    
    payload = {
        'client_id': oauth_settings['CLIENT_ID'],
        'client_secret': oauth_settings['CLIENT_SECRET'],
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': oauth_settings['REDIRECT_URI']
    }
    
    log = TokenRequestLog(
        request_type='auth',
        request_data=payload,
        response_data={}  # Initialize with empty dict
    )
    
    try:
        response = requests.post(token_url, data=payload)
        
        try:
            response_data = response.json()
            logger.info(f"Token exchange response: {json.dumps(response_data, default=str)}")
        except ValueError:
            response_data = {"error": "Invalid JSON response"}
            logger.error(f"Failed to parse JSON response: {response.text[:500]}")
        
        if response.status_code != 200:
            log.status = 'error'
            log.error_message = f"Failed to exchange code for token: {response_data.get('error', 'Unknown error')}"
            log.response_data = response_data
            log.save()
            logger.error(f"OAuth token exchange error: {log.error_message}")
            return JsonResponse({"error": log.error_message}, status=400)
        
        # Calculate token expiry time (24 hours from now)
        expires_at = timezone.now() + timedelta(seconds=response_data.get('expires_in', 86400))
        
        # If we have a location ID from the response, use it
        if 'locationId' in response_data:
            location_id = response_data['locationId']
        
        # Save or update the token
        token, created = OAuth2Token.objects.update_or_create(
            location_id=location_id,
            defaults={
                'access_token': response_data['access_token'],
                'refresh_token': response_data['refresh_token'],
                'expires_at': expires_at
            }
        )
        
        # Fetch location name if not already set
        if created or not token.location_name:
            try:
                # Make a request to the GoHighLevel API to get location details
                location_url = f"https://services.leadconnectorhq.com/locations/{location_id}"
                headers = {
                    'Authorization': f"Bearer {token.access_token}",
                    'Version': '2021-07-28'
                }
                location_response = requests.get(location_url, headers=headers)
                if location_response.status_code == 200:
                    location_data = location_response.json()
                    token.location_name = location_data.get('name', f"Location {location_id}")
                    token.save()
                    logger.info(f"Updated location name to: {token.location_name}")
                else:
                    logger.warning(f"Failed to fetch location name: {location_response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching location name: {str(e)}")
        
        log.token = token
        log.status = 'success'
        log.response_data = {
            'token_type': response_data.get('token_type'),
            'expires_in': response_data.get('expires_in'),
            'scope': response_data.get('scope')
        }
        log.save()
        
        logger.info(f"Successfully {'created' if created else 'updated'} OAuth token for location {location_id}")
        
        # Redirect to admin page for tokens
        return redirect('/admin/crm/oauth2token/')
        
    except Exception as e:
        log.status = 'error'
        log.error_message = f"Exception during token exchange: {str(e)}"
        log.save()
        logger.exception("Exception during OAuth callback")
        return JsonResponse({"error": str(e)}, status=500)

def refresh_token(token):
    """
    Refresh an OAuth token using the refresh token.
    
    Args:
        token: The token to refresh
        
    Returns:
        token: The refreshed token
    """
    try:
        # Log the attempt
        log_system_event(
            f"Attempting to refresh token for location {token.location_id}",
            type='oauth',
            status='in_progress'
        )
        
        # Implement the actual token refresh logic here
        # This is a placeholder for the actual implementation
        
        # For now, we'll just update the token with a new expiration time
        # In a real implementation, you would make a request to the OAuth provider
        
        token_url = get_token_url()
        oauth_settings = settings.GOHIGHLEVEL_OAUTH
        
        payload = {
            'client_id': oauth_settings['CLIENT_ID'],
            'client_secret': oauth_settings['CLIENT_SECRET'],
            'grant_type': 'refresh_token',
            'refresh_token': token.refresh_token
        }
        
        logger.info(f"Refreshing token with payload: {json.dumps(payload, default=str)}")
        
        log = TokenRequestLog(
            token=token,
            request_type='refresh',
            request_data=payload,
            response_data={}  # Initialize with empty dict
        )
        
        try:
            logger.info(f"Sending refresh request to: {token_url}")
            response = requests.post(token_url, data=payload)
            logger.info(f"Received response with status code: {response.status_code}")
            
            try:
                response_data = response.json()
                logger.info(f"Response data: {json.dumps(response_data, default=str)}")
            except ValueError:
                response_data = {"error": "Invalid JSON response", "text": response.text[:500]}
                logger.error(f"Failed to parse JSON response: {response.text[:500]}")
            
            if response.status_code != 200:
                log.status = 'error'
                log.error_message = f"Failed to refresh token: {response_data.get('error', 'Unknown error')}"
                log.response_data = response_data
                log.save()
                logger.error(f"OAuth token refresh error: {log.error_message}")
                return token  # Return the expired token
            
            # Calculate token expiry time (24 hours from now)
            expires_at = timezone.now() + timedelta(seconds=response_data.get('expires_in', 86400))
            
            # Update the token
            token.access_token = response_data['access_token']
            token.refresh_token = response_data['refresh_token']
            token.expires_at = expires_at
            
            # Fetch location name if not already set
            if not token.location_name:
                try:
                    # Make a request to the GoHighLevel API to get location details
                    location_url = f"https://services.leadconnectorhq.com/locations/{token.location_id}"
                    headers = {
                        'Authorization': f"Bearer {token.access_token}",
                        'Version': '2021-07-28'
                    }
                    location_response = requests.get(location_url, headers=headers)
                    if location_response.status_code == 200:
                        location_data = location_response.json()
                        token.location_name = location_data.get('name', f"Location {token.location_id}")
                        logger.info(f"Updated location name to: {token.location_name}")
                    else:
                        logger.warning(f"Failed to fetch location name: {location_response.status_code}")
                except Exception as e:
                    logger.error(f"Error fetching location name: {str(e)}")
            
            token.save()
            
            log.status = 'success'
            log.response_data = {
                'token_type': response_data.get('token_type'),
                'expires_in': response_data.get('expires_in'),
                'scope': response_data.get('scope')
            }
            log.save()
            
            # Log success
            log_system_event(
                f"Successfully refreshed token for location {token.location_id}",
                type='oauth',
                status='success',
                details={
                    'location_id': token.location_id,
                    'expires_at': token.expires_at.isoformat() if token.expires_at else None
                }
            )
            
            logger.info(f"Successfully refreshed OAuth token for location {token.location_id}. New expiry: {expires_at}")
            
            return token
            
        except Exception as e:
            log.status = 'error'
            log.error_message = f"Exception during token refresh: {str(e)}"
            log.save()
            logger.exception(f"Exception during token refresh: {str(e)}")
            # Log error
            log_system_event(
                f"Error refreshing token: {str(e)}",
                type='oauth',
                status='error',
                details={'error': str(e)}
            )
            return token  # Return the expired token
        
    except Exception as e:
        # Log error
        log_system_event(
            f"Error refreshing token: {str(e)}",
            type='oauth',
            status='error',
            details={'error': str(e)}
        )
        logger.exception("Exception during token refresh")
        return token  # Return the expired token

def get_valid_token(location_id):
    """
    Get a valid (non-expired) token for the given location
    """
    try:
        token = OAuth2Token.objects.get(location_id=location_id)
        
        if token.is_expired:
            token = refresh_token(token)
            
        return token
    except OAuth2Token.DoesNotExist:
        logger.error(f"No token found for location {location_id}")
        return None

def get_authorization_url(location_id):
    """
    Generate the authorization URL for the GoHighLevel OAuth flow
    """
    oauth_settings = settings.GOHIGHLEVEL_OAUTH
    
    # Use the authorization URL from settings
    authorization_url = oauth_settings['AUTHORIZATION_URL']
    
    params = {
        'response_type': 'code',
        'client_id': oauth_settings['CLIENT_ID'],
        'redirect_uri': oauth_settings['REDIRECT_URI'],
        'scope': oauth_settings['SCOPE'],
        'locationId': location_id,
        'state': 'ghl_oauth'
    }
    
    # Convert params to query string
    query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
    
    logger.info(f"Generated authorization URL for location {location_id}: {authorization_url}?{query_string}")
    
    return f"{authorization_url}?{query_string}"

def authorize_view(request):
    """
    View to initiate the OAuth flow
    """
    location_id = request.GET.get('location_id', 'pgfekl6sKgofVPSuYOJo')
    
    # Store the location ID in the session for later use
    request.session['ghl_location_id'] = location_id
    
    return redirect(get_authorization_url(location_id))

def refresh_token_view(request, token_id):
    """
    View to manually refresh a token
    """
    try:
        logger.info(f"Refreshing token with ID: {token_id}")
        token = OAuth2Token.objects.get(id=token_id)
        logger.info(f"Found token for location: {token.location_id}")
        
        # Create a log entry for this refresh attempt
        log_entry = TokenRequestLog.objects.create(
            token=token,
            request_type='refresh',
            status='pending',
            request_data={'token_id': str(token_id)},
            response_data={}  # Initialize with empty dict
        )
        
        try:
            refreshed_token = refresh_token(token)
            
            if refreshed_token.is_expired:
                logger.error("Token is still expired after refresh")
                log_entry.status = 'error'
                log_entry.error_message = "Token is still expired after refresh"
                log_entry.save()
                return JsonResponse({"error": "Failed to refresh token"}, status=400)
            
            # Update log entry with success
            log_entry.status = 'success'
            log_entry.response_data = {
                'expires_at': refreshed_token.expires_at.isoformat(),
                'is_expired': refreshed_token.is_expired
            }
            log_entry.save()
            
            logger.info(f"Token refreshed successfully. New expiry: {refreshed_token.expires_at}")
            return redirect('/admin/crm/oauth2token/')
        except Exception as e:
            logger.exception("Exception during token refresh")
            log_entry.status = 'error'
            log_entry.error_message = str(e)
            log_entry.save()
            return JsonResponse({"error": str(e)}, status=500)
    except OAuth2Token.DoesNotExist:
        logger.error(f"Token with ID {token_id} not found")
        return JsonResponse({"error": "Token not found"}, status=404)
    except Exception as e:
        logger.exception("Unexpected exception during token refresh")
        return JsonResponse({"error": str(e)}, status=500)

def location_submit_view(request):
    """
    Handle the submission of a location ID when it wasn't provided in the OAuth callback
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    code = request.POST.get('code')
    location_id = request.POST.get('location_id')
    
    if not code or not location_id:
        return render(request, 'admin/crm/ghl_location_select.html', {
            'title': 'Select GoHighLevel Location',
            'error_message': 'Both code and location ID are required.'
        })
    
    # Store the location ID in the session for future use
    request.session['ghl_location_id'] = location_id
    
    # Exchange the authorization code for an access token
    token_url = get_token_url()
    oauth_settings = settings.GOHIGHLEVEL_OAUTH
    
    payload = {
        'client_id': oauth_settings['CLIENT_ID'],
        'client_secret': oauth_settings['CLIENT_SECRET'],
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': oauth_settings['REDIRECT_URI']
    }
    
    log = TokenRequestLog(
        request_type='auth',
        request_data=payload,
        response_data={}  # Initialize with empty dict
    )
    
    try:
        response = requests.post(token_url, data=payload)
        logger.info(f"Token exchange response status: {response.status_code}")
        
        try:
            response_data = response.json()
            logger.info(f"Token exchange response data: {json.dumps(response_data, default=str)}")
        except ValueError:
            response_data = {"error": "Invalid JSON response"}
            logger.error(f"Failed to parse JSON response: {response.text[:500]}")
        
        if response.status_code != 200:
            log.status = 'error'
            log.error_message = f"Failed to exchange code for token: {response_data.get('error', 'Unknown error')}"
            log.response_data = response_data
            log.save()
            logger.error(f"OAuth token exchange error: {log.error_message}")
            return render(request, 'admin/crm/ghl_location_select.html', {
                'title': 'Select GoHighLevel Location',
                'error_message': f"Failed to exchange code for token: {response_data.get('error', 'Unknown error')}"
            })
        
        # Calculate token expiry time (24 hours from now)
        expires_at = timezone.now() + timedelta(seconds=response_data.get('expires_in', 86400))
        
        # Save or update the token
        token, created = OAuth2Token.objects.update_or_create(
            location_id=location_id,
            defaults={
                'access_token': response_data['access_token'],
                'refresh_token': response_data['refresh_token'],
                'expires_at': expires_at
            }
        )
        
        # Fetch location name if not already set
        if created or not token.location_name:
            try:
                # Make a request to the GoHighLevel API to get location details
                location_url = f"https://services.leadconnectorhq.com/locations/{location_id}"
                headers = {
                    'Authorization': f"Bearer {token.access_token}",
                    'Version': '2021-07-28'
                }
                location_response = requests.get(location_url, headers=headers)
                if location_response.status_code == 200:
                    location_data = location_response.json()
                    token.location_name = location_data.get('name', f"Location {location_id}")
                    token.save()
                    logger.info(f"Updated location name to: {token.location_name}")
                else:
                    logger.warning(f"Failed to fetch location name: {location_response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching location name: {str(e)}")
        
        log.token = token
        log.status = 'success'
        log.response_data = {
            'token_type': response_data.get('token_type'),
            'expires_in': response_data.get('expires_in'),
            'scope': response_data.get('scope')
        }
        log.save()
        
        logger.info(f"Successfully {'created' if created else 'updated'} OAuth token for location {location_id}")
        
        # Redirect to admin page for tokens
        return redirect('/admin/crm/oauth2token/')
        
    except Exception as e:
        log.status = 'error'
        log.error_message = f"Exception during token exchange: {str(e)}"
        log.save()
        logger.exception("Exception during OAuth location submission")
        return render(request, 'admin/crm/ghl_location_select.html', {
            'title': 'Select GoHighLevel Location',
            'error_message': f"An error occurred: {str(e)}"
        })
