#!/usr/bin/env python
"""
GoHighLevel Appointment Webhook Processor

This script processes GoHighLevel appointment webhooks, focusing specifically on
extracting contact information and appointment details as specified.
"""

import os
import sys
import json
import django
import argparse
from datetime import datetime
from django.utils.dateparse import parse_datetime

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doctorsstudio.settings')
django.setup()

# Import models after Django setup
from crm.models import Contact, Appointment, AppointmentWebhookLog
from django.utils import timezone

def process_ghl_appointment(json_file, source='gohighlevel'):
    """
    Process a GoHighLevel appointment webhook from a JSON file.
    Focuses on extracting specific contact and appointment fields.
    """
    try:
        # Load the JSON data
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # Create a webhook log entry
        webhook_log = AppointmentWebhookLog.objects.create(
            source=source,
            headers={},  # Empty headers since we're processing from file
            payload=data,
            status='pending'
        )
        
        print(f"Created webhook log: {webhook_log.id}")
        
        # Extract contact information
        contact_info = {
            'ghl_contact_id': data.get('contact_id'),
            'first_name': data.get('first_name'),
            'last_name': data.get('last_name'),
            'email': data.get('email'),
            'phone': data.get('phone'),
            'address': data.get('address1'),
            'city': data.get('city'),
            'state': data.get('state'),
            'country': data.get('country'),
            'postal_code': data.get('postal_code'),
            'timezone': data.get('timezone')
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
        
        # Find or create contact
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
            print(f"Found existing contact: {contact}")
        else:
            print("No matching contact found")
        
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
            print(f"Updated existing appointment: {appointment.id}")
        else:
            # Create new appointment
            appointment_info['contact'] = contact
            # Remove None values to use model defaults
            appointment_info = {k: v for k, v in appointment_info.items() if v is not None}
            appointment = Appointment.objects.create(**appointment_info)
            print(f"Created new appointment: {appointment.id}")
        
        # Update webhook log
        webhook_log.status = 'success'
        webhook_log.created_appointment = appointment
        webhook_log.save()
        
        # Print appointment details
        print("\nAppointment Details:")
        print(f"ID: {appointment.id}")
        print(f"External ID: {appointment.external_id}")
        print(f"Title: {appointment.title}")
        print(f"Start Time: {appointment.start_time}")
        print(f"End Time: {appointment.end_time}")
        print(f"Status: {appointment.status}")
        print(f"Provider: {appointment.provider}")
        print(f"Service: {appointment.service}")
        print(f"Location: {appointment.location}")
        if appointment.contact:
            print(f"Contact: {appointment.contact}")
        else:
            print("Contact: None")
        
        return appointment
    
    except Exception as e:
        import traceback
        print(f"Error processing appointment: {str(e)}")
        print(traceback.format_exc())
        if 'webhook_log' in locals():
            webhook_log.status = 'error'
            webhook_log.error_message = str(e)
            webhook_log.save()
        return None

def main():
    parser = argparse.ArgumentParser(description='Process GoHighLevel appointment webhook')
    parser.add_argument('json_file', help='Path to JSON file with appointment data')
    parser.add_argument('--source', default='gohighlevel', help='Source identifier for the webhook')
    
    args = parser.parse_args()
    
    appointment = process_ghl_appointment(args.json_file, args.source)
    
    if appointment:
        print("\nSuccessfully processed GoHighLevel appointment!")
    else:
        print("\nFailed to process GoHighLevel appointment.")

if __name__ == '__main__':
    main()
