from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Contact, Order
from .serializers import ContactSerializer, OrderSerializer
import requests
from django.conf import settings
from datetime import datetime

# Create your views here.

class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [AllowAny]

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [AllowAny]

@api_view(['POST'])
@permission_classes([AllowAny])
def sync_woocommerce_data(request):
    # WooCommerce API authentication
    auth = (settings.WOO_CONSUMER_KEY, settings.WOO_CONSUMER_SECRET)
    
    # Fetch customers from WooCommerce
    customers_url = f"{settings.WOO_API_URL}/customers"
    customers_response = requests.get(customers_url, auth=auth)
    
    if customers_response.status_code != 200:
        return Response({"error": "Failed to fetch customers"}, status=400)
    
    customers = customers_response.json()
    
    # Fetch orders from WooCommerce
    orders_url = f"{settings.WOO_API_URL}/orders"
    orders_response = requests.get(orders_url, auth=auth)
    
    if orders_response.status_code != 200:
        return Response({"error": "Failed to fetch orders"}, status=400)
    
    orders = orders_response.json()
    
    # Process customers
    for customer in customers:
        contact, created = Contact.objects.update_or_create(
            email=customer['email'],
            defaults={
                'first_name': customer['first_name'],
                'last_name': customer['last_name'],
                'phone': customer.get('billing', {}).get('phone', ''),
                'billing_address': customer.get('billing', {}).get('address_1', ''),
                'billing_city': customer.get('billing', {}).get('city', ''),
                'billing_state': customer.get('billing', {}).get('state', ''),
                'billing_postcode': customer.get('billing', {}).get('postcode', ''),
            }
        )
    
    # Process orders
    for order in orders:
        contact = Contact.objects.filter(email=order['billing']['email']).first()
        if contact:
            Order.objects.update_or_create(
                woo_order_id=str(order['id']),
                defaults={
                    'contact': contact,
                    'order_date': datetime.fromisoformat(order['date_created'].replace('Z', '+00:00')),
                    'total_amount': order['total'],
                    'status': order['status'],
                }
            )
    
    return Response({"message": "Data synchronized successfully"})
