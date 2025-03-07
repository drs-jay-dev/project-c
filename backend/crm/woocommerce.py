from woocommerce import API
import logging
import json
import requests
from requests.exceptions import RequestException, Timeout
import time
from functools import wraps
from django.conf import settings
import os

# Set up logging to file
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'woocommerce.log')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def retry_on_error(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (RequestException, Timeout) as e:
                    retries += 1
                    if retries == max_retries:
                        raise
                    logger.warning(f"Request failed, retrying ({retries}/{max_retries}): {str(e)}")
                    time.sleep(delay * retries)  # Exponential backoff
            return func(*args, **kwargs)
        return wrapper
    return decorator

class WooCommerceAPI:
    """Class to interact with the WooCommerce API."""
    
    def __init__(self, url=None, consumer_key=None, consumer_secret=None, timeout=30):
        # Use the base URL without /wp-json/wc/v3 as it's added by the API class
        base_url = "https://store.doctorsstudio.com"
        self.consumer_key = consumer_key or "ck_f2926020d6cc2df0f1186f642ba9fac9e949d4fd"
        self.consumer_secret = consumer_secret or "cs_4eb13078eb91058f4facd8870c46f3c6e7ca1745"
        self.timeout = timeout
        
        logger.info(f"Initializing WooCommerce API with URL: {base_url}")
        
        try:
            self.wcapi = API(
                url=base_url,
                consumer_key=self.consumer_key,
                consumer_secret=self.consumer_secret,
                version="wc/v3",
                timeout=self.timeout,
                verify_ssl=False  # For testing only
            )
            self._test_connection()
            logger.info("WooCommerce API initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize WooCommerce API: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    @retry_on_error(max_retries=3)
    def _test_connection(self):
        """Test the WooCommerce API connection."""
        try:
            response = self.wcapi.get("products", params={"per_page": 1})
            if not response.ok:
                logger.error(f"WooCommerce API connection test failed. Status code: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to connect to WooCommerce API. Status code: {response.status_code}")
            logger.info("WooCommerce API connection test successful")
        except Exception as e:
            logger.error(f"WooCommerce API connection error: {str(e)}")
            raise

    @retry_on_error(max_retries=3)
    def get_products(self, page=1, per_page=100):
        """Get products with pagination support and better error handling."""
        try:
            response = self.wcapi.get("products", params={
                "per_page": per_page,
                "page": page,
                "status": "publish"
            })
            
            if not response.ok:
                error_msg = f"Failed to get products. Status code: {response.status_code}"
                if hasattr(response, 'text'):
                    error_msg += f", Response: {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Get headers for pagination
            total_items = int(response.headers.get('X-WP-Total', 0))
            total_pages = int(response.headers.get('X-WP-TotalPages', 0))
            
            # Parse response data
            try:
                data = response.json()
            except Exception as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                raise Exception("Invalid JSON response from WooCommerce API")
            
            if not isinstance(data, list):
                logger.error(f"Invalid response format. Expected list but got: {type(data)}")
                raise Exception("Invalid response format from WooCommerce API")
            
            logger.info(f"Retrieved {len(data)} products. Total pages: {total_pages}, Total items: {total_items}")
            
            return {
                'data': data,
                'total': total_items,
                'total_pages': total_pages,
                'current_page': page
            }
            
        except Exception as e:
            logger.error(f"Error getting products: {str(e)}")
            raise

    @retry_on_error(max_retries=3)
    def get_all_products(self, batch_size=100):
        """
        Get all products using pagination.
        """
        try:
            first_page = self.get_products(page=1, per_page=batch_size)
            if not first_page or 'total' not in first_page:
                logger.error("Failed to get initial product data")
                return []
                
            processed = len(first_page['data'])
            logger.info(f"Processing page 1/{first_page['total_pages']} - {processed}/{first_page['total']} products")
            
            yield first_page['data']
            
            # Process remaining pages
            for page in range(2, first_page['total_pages'] + 1):
                result = self.get_products(page=page, per_page=batch_size)
                if result and result.get('data'):
                    processed += len(result['data'])
                    logger.info(f"Processing page {page}/{first_page['total_pages']} - {processed}/{first_page['total']} products")
                    yield result['data']
                    
        except Exception as e:
            logger.error(f"Error in get_all_products: {str(e)}")
            yield []

    @retry_on_error(max_retries=3)
    def get_orders(self):
        try:
            logger.info("Fetching orders from WooCommerce")
            response = self.wcapi.get("orders", params={"per_page": 100})
            logger.info(f"Orders response status: {response.status_code}")
            logger.debug(f"Orders response: {response.text[:500]}")  # Log first 500 chars of response
            if response.status_code == 200:
                orders = response.json()
                logger.info(f"Retrieved {len(orders)} orders")
                return orders
            else:
                logger.error(f"Failed to get orders: {response.status_code} - {response.text}")
                return []
        except RequestException as e:
            logger.error(f"Network error getting orders: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error getting orders: {str(e)}")
            return []

    @retry_on_error(max_retries=3)
    def get_customers(self, page=1, per_page=100):
        try:
            logger.info(f"Fetching customers from WooCommerce (page {page}, per_page {per_page})")
            # Add role parameter to include both customers and members
            response = self.wcapi.get("customers", params={"per_page": per_page, "page": page, "role": "all"})
            logger.info(f"Customers response status: {response.status_code}")
            logger.debug(f"Customers response: {response.text[:500]}")  # Log first 500 chars of response
            
            if response.status_code == 200:
                # Get headers for pagination
                total_items = int(response.headers.get('X-WP-Total', 0))
                total_pages = int(response.headers.get('X-WP-TotalPages', 0))
                
                # Parse response data
                try:
                    data = response.json()
                except Exception as e:
                    logger.error(f"Failed to parse JSON response: {str(e)}")
                    raise Exception("Invalid JSON response from WooCommerce API")
                
                if not isinstance(data, list):
                    logger.error(f"Invalid response format. Expected list but got: {type(data)}")
                    raise Exception("Invalid response format from WooCommerce API")
                
                logger.info(f"Retrieved {len(data)} customers. Total pages: {total_pages}, Total items: {total_items}")
                
                return {
                    'data': data,
                    'total': total_items,
                    'total_pages': total_pages,
                    'current_page': page
                }
            else:
                logger.error(f"Failed to get customers: {response.status_code} - {response.text}")
                return None
        except RequestException as e:
            logger.error(f"Network error getting customers: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting customers: {str(e)}")
            raise
            
    @retry_on_error(max_retries=3)
    def get_all_customers(self, batch_size=100):
        """
        Get all customers using pagination.
        """
        try:
            first_page = self.get_customers(page=1, per_page=batch_size)
            if not first_page or 'total' not in first_page:
                logger.error("Failed to get initial customer data")
                return []
                
            all_customers = first_page['data']
            processed = len(all_customers)
            logger.info(f"Processing page 1/{first_page['total_pages']} - {processed}/{first_page['total']} customers (including all roles)")
            
            # Process remaining pages
            for page in range(2, first_page['total_pages'] + 1):
                result = self.get_customers(page=page, per_page=batch_size)
                if result and result.get('data'):
                    all_customers.extend(result['data'])
                    processed = len(all_customers)
                    logger.info(f"Processing page {page}/{first_page['total_pages']} - {processed}/{first_page['total']} customers (including all roles)")
                    
            return all_customers
                    
        except Exception as e:
            logger.error(f"Error in get_all_customers: {str(e)}")
            return []
