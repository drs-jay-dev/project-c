"""
GoHighLevel Appointment Webhook Processor

This module provides functions for processing GoHighLevel appointment webhooks,
focusing specifically on extracting contact information and appointment details.
"""

import json
import logging
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import Contact, Appointment, AppointmentWebhookLog

logger = logging.getLogger(__name__)

def process_ghl_appointment_webhook(webhook_log):
    """
    Process a GoHighLevel appointment webhook from a webhook log.
    Extracts contact and appointment information and creates/updates records.
    
    Args:
        webhook_log: An AppointmentWebhookLog instance containing the webhook payload
        
    Returns:
        The created or updated Appointment instance, or None if processing failed
    """
    try:
        data = webhook_log.payload
        source = webhook_log.source
        
        # Extract contact information
        contact_info = {
            'ghl_contact_id': data.get('contact_id'),
            'first_name': data.get('first_name'),
            'last_name': data.get('last_name'),
            'email': data.get('email'),
            'phone': data.get('phone')
        }
        
        # Extract appointment details from calendar data
        calendar_data = data.get('calendar', {})
        
        # Parse and make datetime objects timezone-aware
        start_time_str = calendar_data.get('startTime')
        end_time_str = calendar_data.get('endTime')
        
        # Parse datetime strings and ensure they're timezone-aware
        start_time = parse_datetime(start_time_str) if start_time_str else None
        end_time = parse_datetime(end_time_str) if end_time_str else None
        
        # If parse_datetime didn't return timezone-aware datetimes, make them aware
        if start_time and timezone.is_naive(start_time):
            start_time = timezone.make_aware(start_time)
        if end_time and timezone.is_naive(end_time):
            end_time = timezone.make_aware(end_time)
        
        appointment_info = {
            'external_id': calendar_data.get('appointmentId'),
            'title': calendar_data.get('title'),
            'start_time': start_time,
            'end_time': end_time,
            'status': calendar_data.get('appoinmentStatus', calendar_data.get('status')),
            'provider': f"{data.get('user', {}).get('firstName', '')} {data.get('user', {}).get('lastName', '')}".strip(),
            'service': calendar_data.get('calendarName'),
            'location': calendar_data.get('address'),
            'notes': calendar_data.get('notes', ''),
            'source': source,
            'raw_data': data
        }
        
        # Find or create contact - following the priority order from the memory:
        # ID → Phone → Email
        contact = None
        if contact_info['ghl_contact_id']:
            # Try to find by GoHighLevel ID first (priority 1)
            contact = Contact.objects.filter(ghl_contact_id=contact_info['ghl_contact_id']).first()
        
        if not contact and contact_info['phone']:
            # Try to find by phone (priority 2)
            contact = Contact.objects.filter(phone=contact_info['phone']).first()
        
        if not contact and contact_info['email']:
            # Try to find by email (priority 3)
            contact = Contact.objects.filter(email=contact_info['email']).first()
        
        if contact:
            logger.info(f"Found existing contact: {contact}")
        else:
            logger.info("No matching contact found")
        
        # Create or update appointment
        appointment = None
        if appointment_info['external_id']:
            # Try to find existing appointment by external ID
            appointment = Appointment.objects.filter(external_id=appointment_info['external_id']).first()
        
        if appointment:
            # Update existing appointment
            for key, value in appointment_info.items():
                if value is not None:  # Only update non-None values
                    setattr(appointment, key, value)
            appointment.save()
            logger.info(f"Updated existing appointment: {appointment.id}")
        else:
            # Create new appointment
            appointment_info['contact'] = contact
            # Remove None values to use model defaults
            appointment_info = {k: v for k, v in appointment_info.items() if v is not None}
            appointment = Appointment.objects.create(**appointment_info)
            logger.info(f"Created appointment: {appointment.id}")
        
        # Update webhook log
        webhook_log.status = 'success'
        webhook_log.created_appointment = appointment
        webhook_log.save()
        
        return appointment
    
    except Exception as e:
        logger.error(f"Error processing GoHighLevel appointment: {str(e)}", exc_info=True)
        webhook_log.status = 'error'
        webhook_log.error_message = str(e)
        webhook_log.save()
        return None
