from django.contrib.admin import AdminSite
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta
from .models import Contact, Order, Product, OAuth2Token, SystemLog

class CRMAdminSite(AdminSite):
    site_header = 'DoctorsStudio CRM'
    site_title = 'DoctorsStudio CRM'
    index_title = ''
    
    def get_app_list(self, request, app_label=None):
        """
        Return a sorted list of all the installed apps that have been
        registered in this site.
        """
        app_list = super().get_app_list(request)
        
        # Add OAuth tokens section
        oauth_app = {
            'name': 'OAuth Management',
            'app_label': 'oauth_management',
            'models': [
                {
                    'name': 'OAuth Tokens',
                    'object_name': 'oauth2token',
                    'admin_url': reverse('admin:crm_oauth2token_changelist'),
                    'view_only': False,
                },
                {
                    'name': 'Connect GoHighLevel',
                    'object_name': 'connect',
                    'admin_url': reverse('ghl_oauth_authorize'),
                    'view_only': True,
                },
                {
                    'name': 'Refresh Tokens',
                    'object_name': 'refresh',
                    'admin_url': reverse('admin:index'),  # Replace with actual refresh URL when created
                    'view_only': True,
                },
            ],
        }
        
        # Add GoHighLevel integration section
        ghl_app = {
            'name': 'GoHighLevel',
            'app_label': 'ghl_integration',
            'models': [
                {
                    'name': 'Dashboard',
                    'object_name': 'dashboard',
                    'admin_url': reverse('ghl_dashboard'),
                    'view_only': True,
                },
                {
                    'name': 'Sync Contacts',
                    'object_name': 'sync',
                    'admin_url': reverse('sync_gohighlevel_data'),
                    'view_only': True,
                },
                {
                    'name': 'Sync Dashboard',
                    'object_name': 'sync_dashboard',
                    'admin_url': reverse('sync_dashboard'),
                    'view_only': True,
                },
            ],
        }
        
        # Add WooCommerce integration section
        woo_app = {
            'name': 'WooCommerce',
            'app_label': 'woo_integration',
            'models': [
                {
                    'name': 'Sync Products',
                    'object_name': 'sync_products',
                    'admin_url': reverse('sync_woocommerce_data') + "?type=products",
                    'view_only': True,
                },
                {
                    'name': 'Sync Customers',
                    'object_name': 'sync_customers',
                    'admin_url': reverse('sync_woocommerce_data') + "?type=customers",
                    'view_only': True,
                },
                {
                    'name': 'Sync Orders',
                    'object_name': 'sync_orders',
                    'admin_url': reverse('sync_woocommerce_data') + "?type=orders",
                    'view_only': True,
                },
                {
                    'name': 'Sync Status',
                    'object_name': 'sync_status',
                    'admin_url': reverse('get_sync_status'),
                    'view_only': True,
                },
            ],
        }
        
        # Add system utilities section
        system_app = {
            'name': 'System',
            'app_label': 'system_utilities',
            'models': [
                {
                    'name': 'System Status',
                    'object_name': 'system_status',
                    'admin_url': reverse('system_status'),
                    'view_only': True,
                },
                {
                    'name': 'System Logs',
                    'object_name': 'systemlog',
                    'admin_url': reverse('admin:crm_systemlog_changelist'),
                    'view_only': False,
                },
            ],
        }
        
        # Insert our custom apps at the beginning of the app_list
        app_list.insert(0, oauth_app)
        app_list.insert(1, ghl_app)
        app_list.insert(2, woo_app)
        app_list.insert(3, system_app)
        
        return app_list
    
    def index(self, request, extra_context=None):
        """
        Override the default index view to add custom dashboard data
        """
        # Get counts for dashboard metrics
        contact_count = Contact.objects.count()
        order_count = Order.objects.count()
        product_count = Product.objects.count()
        
        # Check if GoHighLevel is connected
        ghl_connected = OAuth2Token.objects.exists()
        
        # Check if WooCommerce is connected (simplified check - just see if we have any products)
        woo_connected = Product.objects.exists()
        
        # Get last sync time
        last_sync = None
        # First check contacts
        last_contact_sync = Contact.objects.filter(woo_last_sync__isnull=False).order_by('-woo_last_sync').first()
        if last_contact_sync and last_contact_sync.woo_last_sync:
            last_sync = last_contact_sync.woo_last_sync
        
        # Also check GHL sync
        last_ghl_sync = Contact.objects.filter(ghl_last_sync__isnull=False).order_by('-ghl_last_sync').first()
        if last_ghl_sync and last_ghl_sync.ghl_last_sync:
            if not last_sync or last_ghl_sync.ghl_last_sync > last_sync:
                last_sync = last_ghl_sync.ghl_last_sync
        
        # Format last sync time
        if last_sync:
            # If within last 24 hours, show as "Today at HH:MM"
            if last_sync.date() == timezone.now().date():
                last_sync_display = f"Today at {last_sync.strftime('%H:%M')}"
            # If yesterday, show as "Yesterday at HH:MM"
            elif last_sync.date() == (timezone.now() - timedelta(days=1)).date():
                last_sync_display = f"Yesterday at {last_sync.strftime('%H:%M')}"
            # Otherwise show as "MMM DD, YYYY"
            else:
                last_sync_display = last_sync.strftime('%b %d, %Y')
        else:
            last_sync_display = "Never"
        
        # Prepare context
        context = {
            'contact_count': contact_count,
            'order_count': order_count,
            'product_count': product_count,
            'ghl_connected': ghl_connected,
            'woo_connected': woo_connected,
            'last_sync': last_sync_display,
        }
        
        # Update with any extra context
        if extra_context:
            context.update(extra_context)
        
        return super().index(request, context)
    
    def each_context(self, request):
        """Add extra context variables to each admin view."""
        context = super().each_context(request)
        context.update({
            'has_permission': self.has_permission(request),
            'show_sidebar': True,  # Always show the sidebar
        })
        return context

crm_admin_site = CRMAdminSite(name='crm_admin')
