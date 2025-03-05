from django.db.models import Q
from rest_framework import viewsets, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from .models import Contact, Order, Product, OAuth2Token, TokenRequestLog, SystemLog, SyncState
from .serializers import ContactSerializer, OrderSerializer, ProductSerializer
from .woocommerce import WooCommerceAPI
from .woo_sync import sync_woocommerce_contacts, sync_woocommerce_orders, sync_woocommerce_products
from .ghl_sync import sync_all_ghl_contacts, sync_updated_ghl_contacts
import logging
import json
from django.http import JsonResponse
import threading
import time
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.urls import reverse
from .utils import log_system_event
import subprocess
import os

logger = logging.getLogger(__name__)

sync_status = {
    'status': 'idle',
    'message': '',
    'progress': {'current': 0, 'total': 0, 'type': 'products'},
    'should_stop': False
}

# Global variable to track sync status
ghl_sync_status = {
    'running': False,
    'progress': 0,
    'total': 0,
    'completed': 0,
    'errors': 0,
    'message': ''
}

# Global variable to control sync process
stop_sync_flag = False

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class CustomPagination(StandardResultsSetPagination):
    pass

class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.all().order_by('last_name', 'first_name')
    serializer_class = ContactSerializer
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    ordering_fields = ['first_name', 'last_name', 'email']
    ordering = ['last_name', 'first_name']

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )
        return queryset

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by('-order_date')
    serializer_class = OrderSerializer
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['woo_order_id', 'status', 'contact__first_name', 'contact__last_name', 'contact__email']
    ordering_fields = ['order_date', 'total_amount', 'status']
    ordering = ['-order_date']

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(woo_order_id__icontains=search) |
                Q(status__icontains=search) |
                Q(contact__first_name__icontains=search) |
                Q(contact__last_name__icontains=search) |
                Q(contact__email__icontains=search)
            )
        return queryset

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('name')
    serializer_class = ProductSerializer
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'categories']
    ordering_fields = ['name', 'price', 'stock_quantity']
    ordering = ['name']

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(categories__icontains=search)
            )
        return queryset

def process_product(product):
    Product.objects.update_or_create(
        woo_product_id=product['id'],
        defaults={
            'name': product['name'],
            'description': product['description'],
            'price': float(product['price'] or 0),
            'regular_price': float(product.get('regular_price') or 0),
            'sale_price': float(product.get('sale_price') or 0),
            'status': product['status'],
            'stock_status': product.get('stock_status', 'instock'),
            'stock_quantity': product.get('stock_quantity', 0),
            'categories': [cat['name'] for cat in product.get('categories', [])],
            'images': [img['src'] for img in product.get('images', [])],
        }
    )

def process_customer(customer):
    """Process a customer from WooCommerce and create/update in our database."""
    try:
        # First, try to find an existing contact by email (case-insensitive)
        email = customer['email'].lower()
        contact = Contact.objects.filter(email__iexact=email).first()
        
        # Get user role information for logging
        role = "unknown"
        if 'role' in customer:
            role = customer['role']
        
        logger.info(f"Processing customer with email: {email}, role: {role}")
        
        # Log member processing to SystemLog for visibility
        if role and role != 'customer':
            from .utils import log_system_event
            log_system_event(
                message=f"Processing non-customer user: {email} with role: {role}",
                type='sync',
                status='info',
                details={
                    'email': email,
                    'role': role,
                    'woo_id': customer.get('id')
                }
            )
            
        if contact:
            logger.info(f"Found existing contact: ID={contact.id}, WooID={contact.woo_customer_id}, Source={contact.primary_source}")
        else:
            logger.info(f"No existing contact found for email: {email}")
        
        # Prepare the data to update
        contact_data = {
            'woo_customer_id': customer['id'],
            'first_name': customer['first_name'],
            'last_name': customer['last_name'],
            'email': customer['email'],
            'phone': customer['billing'].get('phone', ''),
            'billing_address': customer['billing'].get('address_1', ''),
            'billing_city': customer['billing'].get('city', ''),
            'billing_state': customer['billing'].get('state', ''),
            'billing_postcode': customer['billing'].get('postcode', ''),
            'woo_data': customer,
            'woo_last_sync': timezone.now()
        }
        
        # If contact exists, update it
        if contact:
            # Only set primary_source to 'woo' if it's currently 'crm'
            if contact.primary_source == 'crm':
                contact_data['primary_source'] = 'woo'
                logger.info(f"Changing primary source from 'crm' to 'woo'")
                
            # Update the contact with WooCommerce data
            for key, value in contact_data.items():
                setattr(contact, key, value)
            
            # Save the contact
            try:
                contact.save()
                logger.info(f"Updated existing contact with email {email} from WooCommerce (ID: {customer['id']})")
                return contact
            except Exception as save_error:
                logger.error(f"Error saving contact {contact.id}: {str(save_error)}")
                raise
        else:
            # Create a new contact
            contact_data['primary_source'] = 'woo'  # Set primary source for new contacts
            try:
                contact = Contact.objects.create(**contact_data)
                logger.info(f"Created new contact with email {email} from WooCommerce (ID: {customer['id']})")
                return contact
            except Exception as create_error:
                logger.error(f"Error creating contact with email {email}: {str(create_error)}")
                raise
            
    except Exception as e:
        logger.error(f"Error processing customer {customer.get('id', 'unknown')}: {str(e)}")
        logger.exception("Full exception details:")
        raise

@api_view(['POST'])
def stop_sync(request):
    """Stop the sync process."""
    sync_status['should_stop'] = True
    return JsonResponse({'message': 'Sync process will be stopped'})

@api_view(['POST'])
def update_specific_contact(request):
    """Manually update a specific contact with WooCommerce data."""
    email = request.data.get('email')
    if not email:
        return JsonResponse({'error': 'Email is required'}, status=400)
    
    # Find the contact
    contact = Contact.objects.filter(email__iexact=email).first()
    if not contact:
        return JsonResponse({'error': f'No contact found with email {email}'}, status=404)
    
    # Find the WooCommerce customer
    try:
        wc = WooCommerceAPI()
        customers = wc.get_all_customers()
        matching = [c for c in customers if c.get('email', '').lower() == email.lower()]
        
        if not matching:
            return JsonResponse({'error': f'No WooCommerce customer found with email {email}'}, status=404)
        
        # Process the customer
        customer = matching[0]
        updated_contact = process_customer(customer)
        
        return JsonResponse({
            'message': f'Contact updated successfully',
            'contact_id': str(updated_contact.id),
            'woo_customer_id': updated_contact.woo_customer_id,
            'primary_source': updated_contact.primary_source
        })
    except Exception as e:
        logger.error(f"Error updating contact with email {email}: {str(e)}")
        logger.exception("Full exception details:")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
def update_member_contacts(request):
    """Manually update contacts that have 'member' role instead of 'customer' role."""
    try:
        # Get the emails to check
        emails = request.data.get('emails', [])
        if not emails:
            return JsonResponse({'error': 'At least one email is required'}, status=400)
        
        logger.info(f"Starting update_member_contacts for {len(emails)} emails")
        
        # Initialize WooCommerce API with a shorter timeout
        wc = WooCommerceAPI()
        
        # Log the request
        from .utils import log_system_event
        log_system_event(
            message=f"Processing {len(emails)} contacts in update_member_contacts",
            type='sync',
            status='info',
            details={'emails': emails}
        )
        
        # Get all customers - this might be slow, let's add a timeout
        try:
            logger.info("Fetching all customers from WooCommerce")
            customers = wc.get_all_customers()
            logger.info(f"Retrieved {len(customers)} customers from WooCommerce")
        except Exception as e:
            logger.error(f"Error fetching customers: {str(e)}")
            return JsonResponse({
                'error': f'Error fetching customers: {str(e)}',
                'message': 'The WooCommerce API request timed out. Try with fewer emails or try again later.'
            }, status=500)
        
        results = []
        for email in emails:
            # Find matching WooCommerce user
            logger.info(f"Looking for customer with email: {email}")
            matching = [c for c in customers if c.get('email', '').lower() == email.lower()]
            
            if not matching:
                logger.warning(f"No WooCommerce user found with email: {email}")
                results.append({
                    'email': email,
                    'status': 'error',
                    'message': 'No WooCommerce user found with this email'
                })
                continue
            
            # Process the customer
            customer = matching[0]
            role = customer.get('role', 'unknown')
            logger.info(f"Found customer with email {email}, role: {role}")
            
            try:
                updated_contact = process_customer(customer)
                results.append({
                    'email': email,
                    'status': 'success',
                    'message': f'Contact updated successfully',
                    'role': role,
                    'contact_id': str(updated_contact.id),
                    'woo_customer_id': updated_contact.woo_customer_id,
                    'primary_source': updated_contact.primary_source
                })
                logger.info(f"Successfully updated contact with email: {email}")
            except Exception as e:
                logger.error(f"Error updating contact with email {email}: {str(e)}")
                results.append({
                    'email': email,
                    'status': 'error',
                    'message': f'Error updating contact: {str(e)}',
                    'role': role
                })
        
        # Log completion
        log_system_event(
            message=f"Completed processing {len(emails)} contacts in update_member_contacts",
            type='sync',
            status='success',
            details={'results': results}
        )
        
        return JsonResponse({
            'message': f'Processed {len(results)} contacts',
            'results': results
        })
    except Exception as e:
        logger.error(f"Error in update_member_contacts: {str(e)}")
        logger.exception("Full exception details:")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST', 'GET'])
def sync_woocommerce_data(request):
    """Sync data from WooCommerce."""
    try:
        # Reset stop flag
        sync_status['should_stop'] = False
        
        # Initialize WooCommerce API
        wc = WooCommerceAPI()
        
        # Get sync type from request (either from GET or POST)
        if request.method == 'GET':
            sync_type = request.GET.get('type')
            # For GET requests from admin, return a template
            if request.headers.get('Accept', '').startswith('text/html'):
                return render(request, 'admin/crm/sync_woocommerce.html', {
                    'title': f'Sync WooCommerce {sync_type.title() if sync_type else "Data"}',
                    'site_title': 'DoctorsStudio CRM',
                    'site_header': 'DoctorsStudio CRM Admin',
                    'has_permission': True,
                    'sync_type': sync_type,
                    'valid_types': ['customers', 'products', 'orders'],
                })
        else:
            sync_type = request.data.get('type')
        
        logger.info(f"Received sync request with type: {sync_type}")
        
        # Validate sync type
        valid_types = ['customers', 'products', 'orders']
        if sync_type and sync_type not in valid_types:
            logger.error(f"Invalid sync type received: {sync_type}")
            return JsonResponse({'error': f'Invalid sync type. Must be one of: {", ".join(valid_types)}'}, status=400)
        
        # If no type specified, sync all
        if sync_type:
            sync_types = [sync_type]
            logger.info(f"Will sync only: {sync_type}")
        else:
            sync_types = valid_types
            logger.info("No type specified, will sync all types")
            
        logger.info(f"Will sync the following types: {sync_types}")
            
        for current_type in sync_types:
            logger.info(f"Starting sync for type: {current_type}")
            
            if sync_status['should_stop']:
                sync_status['status'] = 'stopped'
                sync_status['message'] = 'Sync process stopped by user'
                return JsonResponse({'message': 'Sync process stopped', 'status': 'stopped'})
                
            if current_type == 'customers':
                # Sync customers
                sync_status['status'] = 'in_progress'
                sync_status['message'] = 'Starting customer sync...'
                sync_status['progress'] = {'current': 0, 'total': 0, 'type': 'customers', 'success': 0, 'errors': 0}
                
                logger.info("Starting WooCommerce customer sync")
                
                try:
                    # Use the new get_all_customers method to fetch all customers with pagination
                    customers = wc.get_all_customers()
                    
                    if customers:
                        total_customers = len(customers)
                        sync_status['progress']['total'] = total_customers
                        processed_count = 0
                        success_count = 0
                        error_count = 0
                        
                        for customer in customers:
                            if sync_status['should_stop']:
                                sync_status['status'] = 'stopped'
                                sync_status['message'] = f'Sync process stopped by user. Processed {processed_count}/{total_customers} customers. Success: {success_count}, Errors: {error_count}'
                                logger.info(f"Sync stopped by user after processing {processed_count}/{total_customers} customers")
                                return JsonResponse({
                                    'message': 'Sync process stopped', 
                                    'status': 'stopped',
                                    'details': {
                                        'processed': processed_count,
                                        'total': total_customers,
                                        'success': success_count,
                                        'errors': error_count
                                    }
                                })
                            
                            try:
                                process_customer(customer)
                                processed_count += 1
                                success_count += 1
                                sync_status['progress']['current'] = processed_count
                                sync_status['progress']['success'] = success_count
                                sync_status['message'] = f'Processing customer {processed_count}/{total_customers}. Success: {success_count}, Errors: {error_count}'
                                logger.info(f"Processed customer {processed_count}/{total_customers}")
                            except Exception as e:
                                processed_count += 1
                                error_count += 1
                                sync_status['progress']['current'] = processed_count
                                sync_status['progress']['errors'] = error_count
                                error_msg = f"Error processing customer {customer.get('id', 'unknown')}: {str(e)}"
                                logger.error(error_msg)
                                # Log to SystemLog model for admin visibility
                                from .utils import log_system_event
                                log_system_event(
                                    message=error_msg,
                                    type='sync',
                                    status='error',
                                    details={
                                        'customer_id': customer.get('id'),
                                        'error': str(e),
                                        'customer_email': customer.get('email', 'unknown')
                                    }
                                )
                        
                        logger.info(f"Finished processing {processed_count} customers. Success: {success_count}, Errors: {error_count}")
                        sync_status['message'] = f'Completed customer sync. Processed: {processed_count}, Success: {success_count}, Errors: {error_count}'
                    else:
                        sync_status['message'] = 'No customers found to sync'
                        logger.warning("No customers found to sync")
                except Exception as e:
                    error_msg = f"Error fetching customers: {str(e)}"
                    sync_status['message'] = error_msg
                    logger.error(error_msg)
                    from .utils import log_system_event
                    log_system_event(
                        message=error_msg,
                        type='sync',
                        status='error',
                        details={'error': str(e)}
                    )
            
            elif current_type == 'products':
                # Sync products
                sync_status['status'] = 'in_progress'
                sync_status['message'] = 'Starting product sync...'
                sync_status['progress'] = {'current': 0, 'total': 0, 'type': 'products', 'success': 0, 'errors': 0}
                
                logger.info("Starting WooCommerce product sync")
                
                try:
                    # Get products with pagination
                    products_result = wc.get_products()
                    
                    if products_result and 'data' in products_result:
                        products = products_result['data']
                        total_products = products_result['total']
                        sync_status['progress']['total'] = total_products
                        processed_count = 0
                        success_count = 0
                        error_count = 0
                        
                        for product in products:
                            if sync_status['should_stop']:
                                sync_status['status'] = 'stopped'
                                sync_status['message'] = f'Sync process stopped by user. Processed {processed_count}/{total_products} products. Success: {success_count}, Errors: {error_count}'
                                logger.info(f"Sync stopped by user after processing {processed_count}/{total_products} products")
                                return JsonResponse({
                                    'message': 'Sync process stopped', 
                                    'status': 'stopped',
                                    'details': {
                                        'processed': processed_count,
                                        'total': total_products,
                                        'success': success_count,
                                        'errors': error_count
                                    }
                                })
                            
                            try:
                                process_product(product)
                                processed_count += 1
                                success_count += 1
                                sync_status['progress']['current'] = processed_count
                                sync_status['progress']['success'] = success_count
                                sync_status['message'] = f'Processing product {processed_count}/{total_products}. Success: {success_count}, Errors: {error_count}'
                                logger.info(f"Processed product {processed_count}/{total_products}")
                            except Exception as e:
                                processed_count += 1
                                error_count += 1
                                sync_status['progress']['current'] = processed_count
                                sync_status['progress']['errors'] = error_count
                                error_msg = f"Error processing product {product.get('id', 'unknown')}: {str(e)}"
                                logger.error(error_msg)
                                # Log to SystemLog model for admin visibility
                                from .utils import log_system_event
                                log_system_event(
                                    message=error_msg,
                                    type='sync',
                                    status='error',
                                    details={
                                        'product_id': product.get('id'),
                                        'error': str(e),
                                        'product_name': product.get('name', 'unknown')
                                    }
                                )
                        
                        # Process remaining pages
                        current_page = 1
                        total_pages = products_result['total_pages']
                        
                        while current_page < total_pages:
                            current_page += 1
                            
                            if sync_status['should_stop']:
                                sync_status['status'] = 'stopped'
                                sync_status['message'] = f'Sync process stopped by user. Processed {processed_count}/{total_products} products. Success: {success_count}, Errors: {error_count}'
                                logger.info(f"Sync stopped by user after processing {processed_count}/{total_products} products")
                                break
                                
                            try:
                                page_result = wc.get_products(page=current_page)
                                if page_result and 'data' in page_result:
                                    page_products = page_result['data']
                                    
                                    for product in page_products:
                                        if sync_status['should_stop']:
                                            break
                                            
                                        try:
                                            process_product(product)
                                            processed_count += 1
                                            success_count += 1
                                            sync_status['progress']['current'] = processed_count
                                            sync_status['progress']['success'] = success_count
                                            sync_status['message'] = f'Processing product {processed_count}/{total_products}. Success: {success_count}, Errors: {error_count}'
                                            logger.info(f"Processed product {processed_count}/{total_products}")
                                        except Exception as e:
                                            processed_count += 1
                                            error_count += 1
                                            sync_status['progress']['current'] = processed_count
                                            sync_status['progress']['errors'] = error_count
                                            error_msg = f"Error processing product {product.get('id', 'unknown')}: {str(e)}"
                                            logger.error(error_msg)
                                            # Log to SystemLog model for admin visibility
                                            from .utils import log_system_event
                                            log_system_event(
                                                message=error_msg,
                                                type='sync',
                                                status='error',
                                                details={
                                                    'product_id': product.get('id'),
                                                    'error': str(e),
                                                    'product_name': product.get('name', 'unknown')
                                                }
                                            )
                            except Exception as e:
                                error_msg = f"Error fetching product page {current_page}: {str(e)}"
                                logger.error(error_msg)
                                from .utils import log_system_event
                                log_system_event(
                                    message=error_msg,
                                    type='sync',
                                    status='error',
                                    details={'page': current_page, 'error': str(e)}
                                )
                        
                        logger.info(f"Finished processing {processed_count} products. Success: {success_count}, Errors: {error_count}")
                        sync_status['message'] = f'Completed product sync. Processed: {processed_count}, Success: {success_count}, Errors: {error_count}'
                    else:
                        sync_status['message'] = 'No products found to sync'
                        logger.warning("No products found to sync")
                except Exception as e:
                    error_msg = f"Error fetching products: {str(e)}"
                    sync_status['message'] = error_msg
                    logger.error(error_msg)
                    from .utils import log_system_event
                    log_system_event(
                        message=error_msg,
                        type='sync',
                        status='error',
                        details={'error': str(e)}
                    )
            
            elif current_type == 'orders':
                # Sync orders
                sync_status['status'] = 'in_progress'
                sync_status['message'] = 'Starting order sync...'
                sync_status['progress'] = {'current': 0, 'total': 0, 'type': 'orders'}
                
                logger.info("Starting WooCommerce order sync")
                # This will need to be implemented with actual order sync logic
                # For now, just a placeholder
                sync_status['message'] = 'Order sync not implemented yet'
                logger.warning("Order sync not implemented yet")
                
        # If we get here, sync is complete
        sync_status['status'] = 'done'
        sync_status['message'] = 'Sync complete!'
        return JsonResponse({'message': 'Sync complete!', 'status': 'done'})
    
    except Exception as e:
        sync_status['status'] = 'error'
        sync_status['message'] = f'Error: {str(e)}'
        logger.exception(f"Error during sync: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def get_sync_status(request):
    """Get the current status of the sync process."""
    # For GET requests from admin, return a template
    if request.headers.get('Accept', '').startswith('text/html'):
        return render(request, 'admin/crm/sync_status.html', {
            'title': 'Sync Status',
            'site_title': 'DoctorsStudio CRM',
            'site_header': 'DoctorsStudio CRM Admin',
            'has_permission': True,
            'sync_status': sync_status,
        })
    
    return JsonResponse(sync_status)

@staff_member_required
def update_contact_form(request):
    """Admin view for the update contact form."""
    return render(request, 'admin/crm/update_contact.html', {
        'title': 'Update Contact from WooCommerce',
        'site_title': 'DoctorsStudio CRM',
        'site_header': 'DoctorsStudio CRM Admin',
        'has_permission': True,
    })

@staff_member_required
def update_member_contacts_form(request):
    """Admin view for the update member contacts form."""
    return render(request, 'admin/crm/update_member_contacts.html', {
        'title': 'Update Member Contacts',
        'site_title': 'DoctorsStudio CRM',
        'site_header': 'DoctorsStudio CRM Admin',
        'has_permission': True,
    })

@staff_member_required
def contact_dashboard(request):
    """Admin view for contact dashboard."""
    from .models import Contact, Order, Product, SystemLog
    
    # Get counts
    contact_count = Contact.objects.count()
    order_count = Order.objects.count()
    product_count = Product.objects.count()
    
    # Get recent logs
    recent_logs = SystemLog.objects.all().order_by('-timestamp')[:10]
    
    # Get counts by source
    woo_contacts = Contact.objects.filter(woo_customer_id__isnull=False).count()
    ghl_contacts = Contact.objects.filter(ghl_contact_id__isnull=False).count()
    
    return render(request, 'admin/crm/contact_dashboard.html', {
        'title': 'Contact Dashboard',
        'site_title': 'DoctorsStudio CRM',
        'site_header': 'DoctorsStudio CRM Admin',
        'has_permission': True,
        'contact_count': contact_count,
        'order_count': order_count,
        'product_count': product_count,
        'recent_logs': recent_logs,
        'woo_contacts': woo_contacts,
        'ghl_contacts': ghl_contacts,
    })

@api_view(['GET'])
def get_ghl_sync_status(request):
    """
    Get the status of the GoHighLevel sync process
    """
    return JsonResponse(ghl_sync_status)

@api_view(['POST'])
def sync_gohighlevel_data(request):
    """
    Sync data from GoHighLevel
    """
    global ghl_sync_status, stop_sync_flag
    
    if ghl_sync_status['running']:
        return JsonResponse({
            'status': 'error',
            'message': 'Sync already in progress'
        }, status=400)
    
    location_id = request.data.get('location_id')
    if not location_id:
        return JsonResponse({
            'status': 'error',
            'message': 'Location ID is required'
        }, status=400)
    
    # Reset sync status
    ghl_sync_status = {
        'running': True,
        'progress': 0,
        'total': 0,
        'completed': 0,
        'errors': 0,
        'message': 'Starting GoHighLevel sync'
    }
    stop_sync_flag = False
    
    # Start sync in a background thread
    thread = threading.Thread(target=run_ghl_sync, args=(location_id,))
    thread.daemon = True
    thread.start()
    
    return JsonResponse({
        'status': 'success',
        'message': 'GoHighLevel sync started'
    })

def run_ghl_sync(location_id):
    """
    Run the GoHighLevel sync process in a background thread
    """
    global ghl_sync_status, stop_sync_flag
    
    try:
        ghl_sync_status['message'] = 'Syncing GoHighLevel contacts'
        success_count, error_count = sync_all_ghl_contacts(location_id)
        
        ghl_sync_status['completed'] = success_count
        ghl_sync_status['errors'] = error_count
        ghl_sync_status['message'] = f'Completed GoHighLevel sync: {success_count} contacts synced, {error_count} errors'
        ghl_sync_status['progress'] = 100
    except Exception as e:
        logger.exception("Error during GoHighLevel sync")
        ghl_sync_status['message'] = f'Error during GoHighLevel sync: {str(e)}'
        ghl_sync_status['errors'] += 1
    finally:
        ghl_sync_status['running'] = False

@staff_member_required
def ghl_dashboard_view(request):
    """
    Standalone dashboard view for GoHighLevel integration
    """
    tokens = OAuth2Token.objects.all().order_by('-updated_at')
    logs = TokenRequestLog.objects.all().order_by('-created_at')[:10]
    
    context = {
        'tokens': tokens,
        'logs': logs,
        'title': 'GoHighLevel Dashboard',
        'site_title': 'DoctorsStudio CRM',
        'site_header': 'DoctorsStudio CRM Admin',
        'has_permission': True,
    }
    
    return render(request, 'admin/crm/ghl_dashboard.html', context)

@staff_member_required
def sync_dashboard(request):
    """
    Dashboard for monitoring and managing sync operations
    """
    sync_states = SyncState.objects.all().order_by('-last_sync_time')
    tokens = OAuth2Token.objects.all()
    
    # Get recent sync logs
    sync_logs = SystemLog.objects.filter(type='sync').order_by('-timestamp')[:50]
    
    # Get token information
    token_info = []
    for token in tokens:
        expires_at = token.expires_at
        is_expired = False
        status = "Valid"
        
        if expires_at:
            now = timezone.now()
            if expires_at < now:
                is_expired = True
                status = "Expired"
            elif (expires_at - now).total_seconds() < 86400:  # Less than 24 hours
                status = "Expiring Soon"
        
        token_data = {
            'id': token.id,
            'location_id': token.location_id,
            'location_name': f"Location {token.location_id}",  # Use a placeholder since location_name doesn't exist
            'expires_at': expires_at,
            'is_expired': is_expired,
            'status': status
        }
        token_info.append(token_data)
    
    return render(request, 'admin/sync_dashboard.html', {
        'sync_states': sync_states,
        'tokens': token_info,
        'sync_logs': sync_logs,
        'title': 'Sync Dashboard',
    })

@staff_member_required
def start_sync(request):
    """
    Start a new sync operation
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    sync_type = request.POST.get('sync_type')
    location_id = request.POST.get('location_id')
    is_chunked = request.POST.get('chunked', 'false') == 'true'
    chunk_size = int(request.POST.get('chunk_size', '10'))
    chunk_delay = int(request.POST.get('chunk_delay', '60'))
    incremental = request.POST.get('incremental', 'false') == 'true'
    
    if sync_type == 'ghl_contacts':
        if not location_id:
            return JsonResponse({'error': 'Location ID is required'}, status=400)
        
        # Check if a sync is already in progress
        existing_sync = SyncState.objects.filter(
            sync_type=sync_type,
            location_id=location_id,
            is_complete=False
        ).first()
        
        if existing_sync:
            return JsonResponse({
                'error': 'A sync is already in progress for this location',
                'sync_id': str(existing_sync.id)
            }, status=400)
        
        # Create a new sync state
        sync_state = SyncState.objects.create(
            sync_type=sync_type,
            location_id=location_id,
            last_sync_time=timezone.now()
        )
        
        # Build the command
        cmd = ['python', 'manage.py', 'sync_ghl_contacts', 
               f'--location-id={location_id}']
        
        if is_chunked:
            cmd.append('--chunked')
            cmd.append(f'--chunk-size={chunk_size}')
            cmd.append(f'--chunk-delay={chunk_delay}')
        
        if incremental:
            cmd.append('--incremental')
        
        # Log the command
        log_system_event(
            f"Starting sync process with command: {' '.join(cmd)}",
            type='sync',
            status='in_progress',
            details={
                'sync_id': str(sync_state.id),
                'sync_type': sync_type,
                'location_id': location_id,
                'command': ' '.join(cmd)
            }
        )
        
        # Start the process
        try:
            # Run the command in a subprocess
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            
            # Start a thread to monitor the process
            def monitor_process():
                stdout, stderr = process.communicate()
                exit_code = process.wait()
                
                # Update sync state
                sync_state.is_complete = True
                sync_state.save()
                
                # Log completion
                status = 'success' if exit_code == 0 else 'error'
                log_system_event(
                    f"Sync process completed with exit code {exit_code}",
                    type='sync',
                    status=status,
                    details={
                        'sync_id': str(sync_state.id),
                        'exit_code': exit_code,
                        'stdout': stdout[-1000:] if stdout else '',
                        'stderr': stderr[-1000:] if stderr else ''
                    }
                )
            
            thread = threading.Thread(target=monitor_process)
            thread.daemon = True
            thread.start()
            
            return JsonResponse({
                'success': True,
                'message': 'Sync started',
                'sync_id': str(sync_state.id)
            })
            
        except Exception as e:
            # Log the error
            log_system_event(
                f"Error starting sync process: {str(e)}",
                type='sync',
                status='error',
                details={
                    'sync_id': str(sync_state.id),
                    'sync_type': sync_type,
                    'location_id': location_id,
                    'error': str(e)
                }
            )
            
            return JsonResponse({
                'error': f'Failed to start sync: {str(e)}'
            }, status=500)
    
    return JsonResponse({'error': 'Invalid sync type'}, status=400)

@staff_member_required
def sync_status_view(request, sync_id):
    """
    Get the status of a sync operation
    """
    try:
        sync_state = SyncState.objects.get(id=sync_id)
    except SyncState.DoesNotExist:
        return JsonResponse({'error': 'Sync not found'}, status=404)
    
    # Get logs for this sync
    logs = SystemLog.objects.filter(
        type='sync',
        details__sync_id=str(sync_id)
    ).order_by('-timestamp')[:20]
    
    logs_data = [{
        'timestamp': log.timestamp.isoformat(),
        'message': log.message,
        'status': log.status
    } for log in logs]
    
    return JsonResponse({
        'sync_id': str(sync_state.id),
        'sync_type': sync_state.sync_type,
        'location_id': sync_state.location_id,
        'last_page_processed': sync_state.last_page_processed,
        'success_count': sync_state.success_count,
        'error_count': sync_state.error_count,
        'last_sync_time': sync_state.last_sync_time.isoformat() if sync_state.last_sync_time else None,
        'is_complete': sync_state.is_complete,
        'logs': logs_data
    })

@staff_member_required
def cancel_sync(request, sync_id):
    """
    Cancel a running sync operation
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        sync_state = SyncState.objects.get(id=sync_id)
    except SyncState.DoesNotExist:
        return JsonResponse({'error': 'Sync not found'}, status=404)
    
    if sync_state.is_complete:
        return JsonResponse({'error': 'Sync is already complete'}, status=400)
    
    # Mark the sync as complete (cancelled)
    sync_state.is_complete = True
    sync_state.save()
    
    # Log the cancellation
    log_system_event(
        f"Sync cancelled by user",
        type='sync',
        status='warning',
        details={
            'sync_id': str(sync_state.id),
            'sync_type': sync_state.sync_type,
            'location_id': sync_state.location_id
        }
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Sync cancelled'
    })

@staff_member_required
def sync_detail_view(request, sync_id):
    """
    View for a specific sync operation's details
    """
    try:
        sync_state = SyncState.objects.get(id=sync_id)
    except SyncState.DoesNotExist:
        return redirect('sync_dashboard')
    
    return render(request, 'admin/sync_detail.html', {
        'sync_id': sync_id,
        'title': f'Sync Details - {sync_state.sync_type}'
    })

@staff_member_required
def system_status(request):
    """
    View for system status dashboard
    """
    # Get OAuth tokens
    tokens = OAuth2Token.objects.all()
    token_info = []
    
    for token in tokens:
        expires_at = token.expires_at
        is_expired = False
        status = "Valid"
        
        if expires_at:
            now = timezone.now()
            if expires_at < now:
                is_expired = True
                status = "Expired"
            elif (expires_at - now).total_seconds() < 86400:  # Less than 24 hours
                status = "Expiring Soon"
        
        token_data = {
            'id': token.id,
            'location_id': token.location_id,
            'location_name': f"Location {token.location_id}",  # Use a placeholder since location_name doesn't exist
            'expires_at': expires_at,
            'is_expired': is_expired,
            'status': status
        }
        token_info.append(token_data)
    
    # Get sync states
    sync_states = SyncState.objects.all().order_by('-last_sync_time')[:5]
    
    # Get recent sync logs
    sync_logs = SystemLog.objects.filter(type='sync').order_by('-timestamp')[:10]
    
    # Get contact counts
    total_contacts = Contact.objects.count()
    ghl_contacts = Contact.objects.filter(ghl_contact_id__isnull=False).count()
    woo_contacts = Contact.objects.filter(woo_customer_id__isnull=False).count()
    
    # Get last sync times
    last_ghl_sync = Contact.objects.filter(ghl_last_sync__isnull=False).order_by('-ghl_last_sync').first()
    last_woo_sync = Contact.objects.filter(woo_last_sync__isnull=False).order_by('-woo_last_sync').first()
    
    # Calculate sync stats
    ghl_only = Contact.objects.filter(ghl_contact_id__isnull=False, woo_customer_id__isnull=True).count()
    woo_only = Contact.objects.filter(ghl_contact_id__isnull=True, woo_customer_id__isnull=False).count()
    both_sources = Contact.objects.filter(ghl_contact_id__isnull=False, woo_customer_id__isnull=False).count()
    
    # Get primary source stats
    primary_ghl = Contact.objects.filter(primary_source='ghl').count()
    primary_woo = Contact.objects.filter(primary_source='woo').count()
    primary_crm = Contact.objects.filter(primary_source='crm').count()
    
    # Get recent contacts
    recent_contacts = Contact.objects.all().order_by('-created_at')[:5]
    
    # Get contact activity
    contacts_last_24h = Contact.objects.filter(created_at__gte=timezone.now() - timezone.timedelta(hours=24)).count()
    contacts_updated_24h = Contact.objects.filter(updated_at__gte=timezone.now() - timezone.timedelta(hours=24)).count()
    
    return render(request, 'admin/crm/system_status.html', {
        'title': 'System Status',
        'tokens': token_info,
        'sync_states': sync_states,
        'sync_logs': sync_logs,
        'total_contacts': total_contacts,
        'ghl_contacts': ghl_contacts,
        'woo_contacts': woo_contacts,
        'last_ghl_sync': last_ghl_sync.ghl_last_sync if last_ghl_sync else None,
        'last_woo_sync': last_woo_sync.woo_last_sync if last_woo_sync else None,
        'ghl_only': ghl_only,
        'woo_only': woo_only,
        'both_sources': both_sources,
        'primary_ghl': primary_ghl,
        'primary_woo': primary_woo,
        'primary_crm': primary_crm,
        'recent_contacts': recent_contacts,
        'contacts_last_24h': contacts_last_24h,
        'contacts_updated_24h': contacts_updated_24h,
    })
