#!/usr/bin/env python
"""
Appointment Webhook Simulator

This script simulates webhook requests by directly interacting with the Django models
without requiring HTTP requests to localhost. This allows for testing the webhook
functionality in a local development environment.
"""

import os
import sys
import json
import django
import argparse
import datetime
from django.utils import timezone

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doctorsstudio.settings')
django.setup()

# Import models after Django setup
from crm.models import Contact, Appointment, AppointmentWebhookLog
from crm.views import process_appointment_webhook

def simulate_webhook(source='test', contact_email=None, appointment_data=None):
    """
    Simulate a webhook request by directly creating a webhook log and processing it.
    """
    # Create default appointment data if none provided
    if appointment_data is None:
        now = timezone.now()
        end_time = now + datetime.timedelta(hours=1)
        
        appointment_data = {
            'id': f'test-{int(now.timestamp())}',
            'title': 'Test Appointment',
            'start_time': now.isoformat(),
            'end_time': end_time.isoformat(),
            'status': 'scheduled',
            'provider': 'Test Provider',
            'service': 'Test Service',
            'notes': 'This is a test appointment created via the simulator',
            'location': 'Test Location',
        }
    
    # Add contact information if provided
    if contact_email:
        appointment_data['email'] = contact_email
        # Try to find a matching contact
        contact = Contact.objects.filter(email=contact_email).first()
        if contact:
            print(f"Found matching contact: {contact}")
        else:
            print(f"No contact found with email: {contact_email}")
    
    # Create a webhook log entry
    webhook_log = AppointmentWebhookLog.objects.create(
        source=source,
        headers={},  # Empty headers since we're not using HTTP
        payload=appointment_data,
        status='pending'
    )
    
    print(f"Created webhook log: {webhook_log.id}")
    
    # Process the webhook
    try:
        appointment = process_appointment_webhook(webhook_log)
        
        if appointment:
            print("\nCreated/Updated Appointment:")
            print(f"ID: {appointment.id}")
            print(f"Title: {appointment.title}")
            print(f"Start Time: {appointment.start_time}")
            print(f"End Time: {appointment.end_time}")
            print(f"Status: {appointment.status}")
            print(f"Provider: {appointment.provider}")
            print(f"Service: {appointment.service}")
            if appointment.contact:
                print(f"Contact: {appointment.contact}")
            else:
                print("Contact: None")
            
            return True
        else:
            print("Failed to create appointment.")
            return False
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return False

def list_appointments():
    """
    List all appointments in the database.
    """
    appointments = Appointment.objects.all().order_by('-start_time')
    
    if not appointments:
        print("No appointments found.")
        return
    
    print(f"\nFound {appointments.count()} appointments:")
    for idx, appointment in enumerate(appointments, 1):
        contact_info = f" - {appointment.contact}" if appointment.contact else ""
        print(f"{idx}. {appointment.title} ({appointment.start_time.strftime('%Y-%m-%d %H:%M')}){contact_info}")

def list_webhook_logs():
    """
    List all webhook logs in the database.
    """
    logs = AppointmentWebhookLog.objects.all().order_by('-created_at')
    
    if not logs:
        print("No webhook logs found.")
        return
    
    print(f"\nFound {logs.count()} webhook logs:")
    for idx, log in enumerate(logs, 1):
        status_emoji = "✅" if log.status == 'success' else "❌"
        print(f"{idx}. [{status_emoji}] {log.source} - {log.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

def create_from_json(json_file, source='json_import'):
    """
    Create appointments from a JSON file containing appointment data.
    """
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            print(f"Found {len(data)} appointments in JSON file")
            success_count = 0
            
            for item in data:
                if simulate_webhook(source, appointment_data=item):
                    success_count += 1
            
            print(f"\nSuccessfully processed {success_count} out of {len(data)} appointments")
        else:
            # Single appointment
            if simulate_webhook(source, appointment_data=data):
                print("\nSuccessfully processed appointment from JSON")
            else:
                print("\nFailed to process appointment from JSON")
    
    except Exception as e:
        print(f"Error processing JSON file: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Simulate appointment webhooks')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Create appointment command
    create_parser = subparsers.add_parser('create', help='Create a test appointment')
    create_parser.add_argument('--source', default='test', help='Source of the webhook')
    create_parser.add_argument('--email', help='Email to associate with the appointment')
    
    # Import from JSON command
    import_parser = subparsers.add_parser('import', help='Import appointments from JSON file')
    import_parser.add_argument('json_file', help='Path to JSON file with appointment data')
    import_parser.add_argument('--source', default='json_import', help='Source of the webhook')
    
    # List appointments command
    list_parser = subparsers.add_parser('list', help='List all appointments')
    
    # List webhook logs command
    logs_parser = subparsers.add_parser('logs', help='List all webhook logs')
    
    args = parser.parse_args()
    
    if args.command == 'create':
        if simulate_webhook(args.source, args.email):
            print("\nTest appointment created successfully!")
        else:
            print("\nFailed to create test appointment.")
    elif args.command == 'import':
        create_from_json(args.json_file, args.source)
    elif args.command == 'list':
        list_appointments()
    elif args.command == 'logs':
        list_webhook_logs()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
