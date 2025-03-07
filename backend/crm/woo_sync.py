import logging
from django.utils import timezone
from .models import Contact, Order, Product
from .woocommerce import WooCommerceAPI

logger = logging.getLogger(__name__)

def sync_woocommerce_contacts(api=None):
    """
    Sync contacts from WooCommerce
    
    Args:
        api (WooCommerceAPI): Optional WooCommerce API instance
        
    Returns:
        tuple: (success_count, error_count)
    """
    if api is None:
        api = WooCommerceAPI()
    
    page = 1
    per_page = 100
    success_count = 0
    error_count = 0
    
    while True:
        try:
            customers = api.get_customers(page=page, per_page=per_page)
            
            if not customers:
                break
            
            for customer_data in customers:
                try:
                    woo_id = customer_data.get('id')
                    if not woo_id:
                        continue
                    
                    # Try to find an existing contact by WooCommerce ID
                    contact = Contact.objects.filter(woo_id=woo_id).first()
                    
                    # If not found by WooCommerce ID, try by email
                    if not contact:
                        email = customer_data.get('email')
                        if email:
                            contact = Contact.objects.filter(email=email).first()
                    
                    # Extract contact data
                    contact_data = {
                        'first_name': customer_data.get('first_name', ''),
                        'last_name': customer_data.get('last_name', ''),
                        'email': customer_data.get('email', ''),
                        'woo_id': woo_id,
                        'woo_data': customer_data,
                    }
                    
                    # Get phone from billing info if available
                    billing = customer_data.get('billing', {})
                    if billing and 'phone' in billing:
                        contact_data['phone'] = billing.get('phone', '')
                    
                    # Create or update the contact
                    if contact:
                        # Update existing contact
                        for key, value in contact_data.items():
                            setattr(contact, key, value)
                        
                        # If this is the first time we're adding WooCommerce data to an existing contact
                        if 'woo' not in contact.source:
                            contact.source = list(set(contact.source + ['woo']))
                        
                        contact.date_updated = timezone.now()
                        contact.save()
                        logger.info(f"Updated contact {contact.id} with WooCommerce data")
                    else:
                        # Create new contact
                        contact_data['source'] = ['woo']
                        contact = Contact.objects.create(**contact_data)
                        logger.info(f"Created new contact {contact.id} from WooCommerce data")
                    
                    success_count += 1
                except Exception as e:
                    logger.exception(f"Error syncing WooCommerce customer {customer_data.get('id')}: {str(e)}")
                    error_count += 1
            
            # If we got fewer results than requested, we've reached the end
            if len(customers) < per_page:
                break
            
            page += 1
        except Exception as e:
            logger.exception(f"Error fetching WooCommerce customers page {page}: {str(e)}")
            error_count += 1
            break
    
    return success_count, error_count

def sync_woocommerce_orders(api=None):
    """
    Sync orders from WooCommerce
    
    Args:
        api (WooCommerceAPI): Optional WooCommerce API instance
        
    Returns:
        tuple: (success_count, error_count)
    """
    if api is None:
        api = WooCommerceAPI()
    
    page = 1
    per_page = 100
    success_count = 0
    error_count = 0
    
    while True:
        try:
            orders = api.get_orders(page=page, per_page=per_page)
            
            if not orders:
                break
            
            for order_data in orders:
                try:
                    woo_id = order_data.get('id')
                    if not woo_id:
                        continue
                    
                    # Try to find an existing order by WooCommerce ID
                    order = Order.objects.filter(woo_id=woo_id).first()
                    
                    # Find the contact for this order
                    customer_id = order_data.get('customer_id')
                    contact = None
                    
                    if customer_id:
                        contact = Contact.objects.filter(woo_id=customer_id).first()
                    
                    if not contact and 'billing' in order_data:
                        billing = order_data.get('billing', {})
                        email = billing.get('email')
                        
                        if email:
                            contact = Contact.objects.filter(email=email).first()
                    
                    # If we still don't have a contact, create one from the order data
                    if not contact and 'billing' in order_data:
                        billing = order_data.get('billing', {})
                        
                        contact_data = {
                            'first_name': billing.get('first_name', ''),
                            'last_name': billing.get('last_name', ''),
                            'email': billing.get('email', ''),
                            'phone': billing.get('phone', ''),
                            'source': ['woo'],
                            'woo_data': {
                                'billing': billing
                            }
                        }
                        
                        contact = Contact.objects.create(**contact_data)
                        logger.info(f"Created new contact {contact.id} from WooCommerce order data")
                    
                    if not contact:
                        logger.warning(f"Could not find or create contact for order {woo_id}")
                        continue
                    
                    # Extract order data
                    order_data_dict = {
                        'contact': contact,
                        'woo_id': woo_id,
                        'order_number': order_data.get('number', ''),
                        'status': order_data.get('status', ''),
                        'total': float(order_data.get('total', 0)),
                        'woo_data': order_data,
                    }
                    
                    # Create or update the order
                    if order:
                        # Update existing order
                        for key, value in order_data_dict.items():
                            setattr(order, key, value)
                        
                        order.date_updated = timezone.now()
                        order.save()
                        logger.info(f"Updated order {order.id} with WooCommerce data")
                    else:
                        # Create new order
                        order = Order.objects.create(**order_data_dict)
                        logger.info(f"Created new order {order.id} from WooCommerce data")
                    
                    success_count += 1
                except Exception as e:
                    logger.exception(f"Error syncing WooCommerce order {order_data.get('id')}: {str(e)}")
                    error_count += 1
            
            # If we got fewer results than requested, we've reached the end
            if len(orders) < per_page:
                break
            
            page += 1
        except Exception as e:
            logger.exception(f"Error fetching WooCommerce orders page {page}: {str(e)}")
            error_count += 1
            break
    
    return success_count, error_count

def sync_woocommerce_products(api=None):
    """
    Sync products from WooCommerce
    
    Args:
        api (WooCommerceAPI): Optional WooCommerce API instance
        
    Returns:
        tuple: (success_count, error_count)
    """
    if api is None:
        api = WooCommerceAPI()
    
    page = 1
    per_page = 100
    success_count = 0
    error_count = 0
    
    while True:
        try:
            products = api.get_products(page=page, per_page=per_page)
            
            if not products:
                break
            
            for product_data in products:
                try:
                    woo_id = product_data.get('id')
                    if not woo_id:
                        continue
                    
                    # Try to find an existing product by WooCommerce ID
                    product = Product.objects.filter(woo_id=woo_id).first()
                    
                    # Extract product data
                    product_data_dict = {
                        'name': product_data.get('name', ''),
                        'sku': product_data.get('sku', ''),
                        'price': float(product_data.get('price', 0)),
                        'woo_id': woo_id,
                        'woo_data': product_data,
                    }
                    
                    # Create or update the product
                    if product:
                        # Update existing product
                        for key, value in product_data_dict.items():
                            setattr(product, key, value)
                        
                        product.date_updated = timezone.now()
                        product.save()
                        logger.info(f"Updated product {product.id} with WooCommerce data")
                    else:
                        # Create new product
                        product = Product.objects.create(**product_data_dict)
                        logger.info(f"Created new product {product.id} from WooCommerce data")
                    
                    success_count += 1
                except Exception as e:
                    logger.exception(f"Error syncing WooCommerce product {product_data.get('id')}: {str(e)}")
                    error_count += 1
            
            # If we got fewer results than requested, we've reached the end
            if len(products) < per_page:
                break
            
            page += 1
        except Exception as e:
            logger.exception(f"Error fetching WooCommerce products page {page}: {str(e)}")
            error_count += 1
            break
    
    return success_count, error_count
