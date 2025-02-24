from django.db.models import Q
from rest_framework import viewsets, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import Contact, Order, Product
from .serializers import ContactSerializer, OrderSerializer, ProductSerializer
from .woocommerce import WooCommerceAPI
import logging
import json
from django.http import JsonResponse

logger = logging.getLogger(__name__)

sync_status = {
    'status': 'idle',
    'message': '',
    'progress': {'current': 0, 'total': 0, 'type': 'products'},
    'should_stop': False
}

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
    Contact.objects.update_or_create(
        woo_customer_id=customer['id'],
        defaults={
            'first_name': customer['first_name'],
            'last_name': customer['last_name'],
            'email': customer['email'],
            'phone': customer['billing'].get('phone', ''),
            'billing_address': customer['billing'].get('address_1', ''),
            'billing_city': customer['billing'].get('city', ''),
            'billing_state': customer['billing'].get('state', ''),
            'billing_postcode': customer['billing'].get('postcode', '')
        }
    )

@api_view(['POST'])
def stop_sync(request):
    """Stop the ongoing sync process."""
    sync_status['should_stop'] = True
    sync_status['status'] = 'stopping'
    sync_status['message'] = 'Stopping sync process...'
    return JsonResponse({'message': 'Stopping sync process'})

@api_view(['POST'])
def sync_woocommerce_data(request):
    """Sync data from WooCommerce."""
    try:
        # Reset stop flag
        sync_status['should_stop'] = False
        
        # Initialize WooCommerce API
        wc = WooCommerceAPI()
        
        # Get sync type from request
        sync_type = request.data.get('type')
        logger.info(f"Received sync request with type: {sync_type}")
        logger.info(f"Request data: {request.data}")
        logger.info(f"Request content type: {request.content_type}")
        logger.info(f"Request headers: {request.headers}")
        
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
                sync_status['progress'] = {'current': 0, 'total': 0, 'type': 'customers'}
                
                logger.info("Starting WooCommerce customer sync")
                customers = wc.get_customers()
                
                if customers:
                    total_customers = len(customers)
                    sync_status['progress']['total'] = total_customers
                    processed_count = 0
                    
                    for customer in customers:
                        if sync_status['should_stop']:
                            sync_status['status'] = 'stopped'
                            sync_status['message'] = 'Sync process stopped by user'
                            return JsonResponse({'message': 'Sync process stopped', 'status': 'stopped'})
                        
                        try:
                            process_customer(customer)
                            processed_count += 1
                            sync_status['progress']['current'] = processed_count
                            sync_status['message'] = f'Processing customer {processed_count}/{total_customers}'
                            logger.info(f"Processed customer {processed_count}/{total_customers}")
                        except Exception as e:
                            logger.error(f"Error processing customer: {str(e)}")
                
                if sync_type == 'customers':
                    logger.info("Completed customers sync, returning response")
                    sync_status['status'] = 'success'
                    sync_status['message'] = 'Customer sync completed successfully'
                    return JsonResponse({'message': 'Customer sync completed successfully', 'status': 'success'})
                else:
                    logger.info("Completed customers sync, continuing to next type")

            elif current_type == 'products':
                # Sync products
                sync_status['status'] = 'in_progress'
                sync_status['message'] = 'Starting product sync...'
                sync_status['progress'] = {'current': 0, 'total': 0, 'type': 'products'}
                
                logger.info("Starting WooCommerce product sync")
                
                # Get first page to determine total
                first_page = wc.get_products(page=1)
                if not first_page or 'total' not in first_page:
                    raise Exception("Failed to get product count from WooCommerce")
                    
                total_products = first_page['total']
                logger.info(f"Found {total_products} products to sync")
                
                sync_status['progress']['total'] = total_products
                processed_count = 0
                
                # Process first page results
                if first_page.get('data'):
                    for product in first_page['data']:
                        if sync_status['should_stop']:
                            sync_status['status'] = 'stopped'
                            sync_status['message'] = 'Sync process stopped by user'
                            return JsonResponse({'message': 'Sync process stopped', 'status': 'stopped'})
                            
                        try:
                            process_product(product)
                            processed_count += 1
                            sync_status['progress']['current'] = processed_count
                            sync_status['message'] = f'Processing product {processed_count}/{total_products}'
                            logger.info(f"Processed product {processed_count}/{total_products}")
                        except Exception as e:
                            logger.error(f"Error processing product: {str(e)}")
                            
                # Process remaining pages
                current_page = 2
                total_pages = first_page.get('total_pages', 1)
                
                while current_page <= total_pages and processed_count < total_products:
                    if sync_status['should_stop']:
                        sync_status['status'] = 'stopped'
                        sync_status['message'] = 'Sync process stopped by user'
                        return JsonResponse({'message': 'Sync process stopped', 'status': 'stopped'})
                        
                    try:
                        logger.info(f"Processing page {current_page}/{total_pages}")
                        result = wc.get_products(page=current_page)
                        
                        if result and result.get('data'):
                            for product in result['data']:
                                if sync_status['should_stop']:
                                    sync_status['status'] = 'stopped'
                                    sync_status['message'] = 'Sync process stopped by user'
                                    return JsonResponse({'message': 'Sync process stopped', 'status': 'stopped'})
                                    
                                try:
                                    process_product(product)
                                    processed_count += 1
                                    sync_status['progress']['current'] = processed_count
                                    sync_status['message'] = f'Processing product {processed_count}/{total_products}'
                                    logger.info(f"Processed product {processed_count}/{total_products}")
                                except Exception as e:
                                    logger.error(f"Error processing product: {str(e)}")
                                    continue
                                    
                        current_page += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing page {current_page}: {str(e)}")
                        sync_status['status'] = 'error'
                        sync_status['message'] = f'Error during sync: {str(e)}'
                        return JsonResponse({'error': str(e)}, status=500)

                if sync_type == 'products':
                    logger.info("Completed products sync, returning response")
                    sync_status['status'] = 'success'
                    sync_status['message'] = 'Product sync completed successfully'
                    return JsonResponse({'message': 'Product sync completed successfully', 'status': 'success'})
                else:
                    logger.info("Completed products sync, continuing to next type")

            elif current_type == 'orders':
                # Sync orders
                sync_status['status'] = 'in_progress'
                sync_status['message'] = 'Starting order sync...'
                sync_status['progress'] = {'current': 0, 'total': 0, 'type': 'orders'}
                
                logger.info("Starting WooCommerce order sync")
                orders = wc.get_orders()
                
                if orders:
                    total_orders = len(orders)
                    sync_status['progress']['total'] = total_orders
                    processed_count = 0
                    
                    for order in orders:
                        if sync_status['should_stop']:
                            sync_status['status'] = 'stopped'
                            sync_status['message'] = 'Sync process stopped by user'
                            return JsonResponse({'message': 'Sync process stopped', 'status': 'stopped'})
                        
                        try:
                            # TODO: Add process_order function
                            processed_count += 1
                            sync_status['progress']['current'] = processed_count
                            sync_status['message'] = f'Processing order {processed_count}/{total_orders}'
                            logger.info(f"Processed order {processed_count}/{total_orders}")
                        except Exception as e:
                            logger.error(f"Error processing order: {str(e)}")

                if sync_type == 'orders':
                    logger.info("Completed orders sync, returning response")
                    sync_status['status'] = 'success'
                    sync_status['message'] = 'Order sync completed successfully'
                    return JsonResponse({'message': 'Order sync completed successfully', 'status': 'success'})
                else:
                    logger.info("Completed orders sync, continuing to next type")

        # Only reach here if no specific type was specified (syncing all)
        logger.info("Completed all sync operations")
        sync_status['status'] = 'success'
        sync_status['message'] = 'All sync operations completed successfully'
        return JsonResponse({'message': 'All sync operations completed successfully', 'status': 'success'})

    except Exception as e:
        logger.error(f"Error syncing with WooCommerce: {str(e)}")
        sync_status['status'] = 'error'
        sync_status['message'] = f'Error during sync: {str(e)}'
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def get_sync_status(request):
    return Response(sync_status)
