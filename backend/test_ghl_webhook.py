#!/usr/bin/env python 3/8/2025 update on webhook endpoint with sample data
"""
GoHighLevel Webhook Testing Tool

This script allows testing the GoHighLevel webhook integration without needing
to send to a localhost URL. It simulates GoHighLevel webhook requests using
the sample payload provided.
"""

import os
import sys
import json
import django
import argparse
from datetime import datetime

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doctorsstudio.settings')
django.setup()

# Import models after Django setup
from crm.models import Contact, Appointment, AppointmentWebhookLog
from crm.ghl_processor import process_ghl_appointment_webhook

def simulate_ghl_webhook(json_file=None, contact_email=None):
    """
    Simulate a GoHighLevel webhook request using either a JSON file or by
    creating a sample payload with the specified contact email.
    """
    # Load the payload from the JSON file if provided
    if json_file:
        try:
            with open(json_file, 'r') as f:
                payload = json.load(f)
        except Exception as e:
            print(f"Error loading JSON file: {str(e)}")
            return False
    else:
        # Create a sample payload
        now = datetime.now().isoformat()
        payload = {
            "contact_id": f"test-{int(datetime.now().timestamp())}",
            "first_name": "Test",
            "last_name": "User",
            "full_name": "Test User",
            "email": contact_email or f"test-{int(datetime.now().timestamp())}@example.com",
            "phone": "+11234567890",
            "address1": "123 Test St",
            "city": "Test City",
            "state": "Test State",
            "country": "US",
            "timezone": "America/New_York",
            "postal_code": "12345",
            "user": {
                "firstName": "Test",
                "lastName": "Provider",
                "email": "provider@example.com"
            },
            "calendar": {
                "id": f"test-{int(datetime.now().timestamp())}",
                "title": "Test Appointment",
                "calendarName": "Test Calendar",
                "selectedTimezone": "America/New_York",
                "appointmentId": f"test-{int(datetime.now().timestamp())}",
                "startTime": now,
                "endTime": now,
                "status": "booked",
                "appoinmentStatus": "confirmed",
                "address": "123 Test St, Test City, Test State 12345",
                "notes": "Test appointment notes",
                "date_created": now
            },
            "last_updated_by_meta": {
                "source": "test_script",
                "channel": "test"
            }
        }
    
    # Create a webhook log entry
    webhook_log = AppointmentWebhookLog.objects.create(
        source='gohighlevel',
        headers={},  # Empty headers since we're not using HTTP
        payload=payload,
        status='pending'
    )
    
    print(f"Created webhook log: {webhook_log.id}")
    
    # Process the webhook
    try:
        appointment = process_ghl_appointment_webhook(webhook_log)
        
        if appointment:
            print("\nSuccessfully processed GoHighLevel appointment:")
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
            
            return True
        else:
            print("Failed to process GoHighLevel appointment.")
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

def main():
    parser = argparse.ArgumentParser(description='Test GoHighLevel webhook integration')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Simulate webhook command
    simulate_parser = subparsers.add_parser('simulate', help='Simulate a GoHighLevel webhook')
    simulate_parser.add_argument('--file', help='Path to JSON file with webhook payload')
    simulate_parser.add_argument('--email', help='Email to associate with the appointment')
    
    # List appointments command
    list_parser = subparsers.add_parser('list', help='List all appointments')
    
    # List webhook logs command
    logs_parser = subparsers.add_parser('logs', help='List all webhook logs')
    
    args = parser.parse_args()
    
    if args.command == 'simulate':
        success = simulate_ghl_webhook(args.file, args.email)
        if success:
            print("\nGoHighLevel webhook simulation completed successfully!")
        else:
            print("\nGoHighLevel webhook simulation failed.")
    elif args.command == 'list':
        list_appointments()
    elif args.command == 'logs':
        list_webhook_logs()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
