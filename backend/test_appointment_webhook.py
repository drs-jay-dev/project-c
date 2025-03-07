#!/usr/bin/env python 3/8/2025 update on webhook endpoint with sample data
"""
Test script for the Appointment Webhook endpoint.
This script simulates webhook requests to the appointment endpoint
without requiring external access to localhost.
"""

import os
import sys
import json
import django
import argparse
import datetime

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doctorsstudio.settings')
django.setup()

from django.test.client import Client
from django.utils import timezone
from crm.models import Appointment, AppointmentWebhookLog, Contact

def create_test_appointment(source='test', contact_email=None):
    """
    Create a test appointment using the Django test client.
    This simulates a webhook request without requiring an actual HTTP request.
    """
    client = Client()
    
    # Create a sample appointment payload
    now = timezone.now()
    end_time = now + datetime.timedelta(hours=1)
    
    payload = {
        'id': f'test-{int(now.timestamp())}',
        'title': 'Test Appointment',
        'start_time': now.isoformat(),
        'end_time': end_time.isoformat(),
        'status': 'scheduled',
        'provider': 'Test Provider',
        'service': 'Test Service',
        'notes': 'This is a test appointment created via the test script',
        'location': 'Test Location',
    }
    
    # Add contact information if provided
    if contact_email:
        payload['email'] = contact_email
        # Try to find a matching contact
        contact = Contact.objects.filter(email=contact_email).first()
        if contact:
            print(f"Found matching contact: {contact}")
        else:
            print(f"No contact found with email: {contact_email}")
    
    # Make the request to the webhook endpoint
    response = client.post(
        f'/api/webhooks/appointments/?source={source}',
        data=json.dumps(payload),
        content_type='application/json'
    )
    
    # Print the response
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # If successful, get and print the created appointment
    if response.status_code == 200 and 'webhook_id' in response.json():
        webhook_id = response.json()['webhook_id']
        webhook_log = AppointmentWebhookLog.objects.get(id=webhook_id)
        
        if webhook_log.created_appointment:
            appointment = webhook_log.created_appointment
            print("\nCreated Appointment:")
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
    
    return response.status_code == 200

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

def main():
    parser = argparse.ArgumentParser(description='Test the appointment webhook endpoint')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Create appointment command
    create_parser = subparsers.add_parser('create', help='Create a test appointment')
    create_parser.add_argument('--source', default='test', help='Source of the webhook')
    create_parser.add_argument('--email', help='Email to associate with the appointment')
    
    # List appointments command
    list_parser = subparsers.add_parser('list', help='List all appointments')
    
    # List webhook logs command
    logs_parser = subparsers.add_parser('logs', help='List all webhook logs')
    
    args = parser.parse_args()
    
    if args.command == 'create':
        success = create_test_appointment(args.source, args.email)
        if success:
            print("\nTest appointment created successfully!")
        else:
            print("\nFailed to create test appointment.")
    elif args.command == 'list':
        list_appointments()
    elif args.command == 'logs':
        list_webhook_logs()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
