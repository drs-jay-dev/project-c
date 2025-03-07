from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from .models import Contact, Order, Product, OAuth2Token, TokenRequestLog, SystemLog, Appointment, AppointmentWebhookLog
from .admin_site import crm_admin_site
from .ghl_oauth import get_authorization_url
from django.contrib import messages
import psutil
import datetime

# Register your models here.

class HasWooFilter(admin.SimpleListFilter):
    """Filter contacts by WooCommerce integration status"""
    title = _('Has WooCommerce')
    parameter_name = 'has_woo'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', _('Yes')),
            ('no', _('No')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(woo_customer_id__isnull=True)
        if self.value() == 'no':
            return queryset.filter(woo_customer_id__isnull=True)

class HasGHLFilter(admin.SimpleListFilter):
    """Filter contacts by GoHighLevel integration status"""
    title = _('Has GoHighLevel')
    parameter_name = 'has_ghl'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', _('Yes')),
            ('no', _('No')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(ghl_contact_id__isnull=True)
        if self.value() == 'no':
            return queryset.filter(ghl_contact_id__isnull=True)

class CombinedSourceFilter(admin.SimpleListFilter):
    """Filter contacts by combined data sources"""
    title = _('Source')
    parameter_name = 'combined_source'
    
    def lookups(self, request, model_admin):
        return (
            ('woo_only', _('WooCommerce Only')),
            ('ghl_only', _('GoHighLevel Only')),
            ('both', _('Both WooCommerce and GoHighLevel')),
            ('neither', _('Neither WooCommerce nor GoHighLevel')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'woo_only':
            return queryset.exclude(woo_customer_id__isnull=True).filter(ghl_contact_id__isnull=True)
        if self.value() == 'ghl_only':
            return queryset.filter(woo_customer_id__isnull=True).exclude(ghl_contact_id__isnull=True)
        if self.value() == 'both':
            return queryset.exclude(woo_customer_id__isnull=True).exclude(ghl_contact_id__isnull=True)
        if self.value() == 'neither':
            return queryset.filter(woo_customer_id__isnull=True, ghl_contact_id__isnull=True)

class ContactAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Core Contact Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'normalized_phone',
                      'billing_address', 'billing_city', 'billing_state', 'billing_postcode')
        }),
        ('Integration Status', {
            'fields': ('primary_source', 'sources_display',
                      'woo_customer_id', 'woo_last_sync',
                      'ghl_contact_id', 'ghl_last_sync'),
            'classes': ('collapse',),
        }),
        ('GoHighLevel Data', {
            'fields': ('ghl_tags', 'ghl_custom_fields', 'ghl_data'),
            'classes': ('collapse',),
        }),
        ('WooCommerce Data', {
            'fields': ('woo_data',),
            'classes': ('collapse',),
        }),
        ('System Fields', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    list_display = ('id', 'first_name', 'last_name', 'email', 'phone', 'created_at', 'has_woo', 'has_ghl')
    search_fields = ('first_name', 'last_name', 'email', 'phone')
    list_filter = ('created_at', 'primary_source', HasWooFilter, HasGHLFilter, CombinedSourceFilter)
    readonly_fields = ('id', 'created_at', 'updated_at', 'sources_display')
    
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()
    full_name.short_description = 'Name'
    
    def has_woo(self, obj):
        return obj.has_woo
    has_woo.boolean = True
    has_woo.short_description = 'WooCommerce'
    
    def has_ghl(self, obj):
        return obj.has_ghl
    has_ghl.boolean = True
    has_ghl.short_description = 'GoHighLevel'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('update-from-woocommerce/', self.admin_site.admin_view(self.update_from_woocommerce_view), name='update-from-woocommerce'),
        ]
        return custom_urls + urls
    
    def update_from_woocommerce_view(self, request):
        # Redirect to the update contact form
        return redirect('/api/sync/update-contact-form/')
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_update_from_woo_button'] = True
        return super().change_view(request, object_id, form_url, extra_context)
    
    def sources_display(self, obj):
        """Display all sources for this contact with colored tags"""
        sources_html = []
        
        if obj.has_woo:
            tag_style = "background-color: purple; color: white; padding: 3px 7px; border-radius: 10px; margin-right: 5px; display: inline-block;"
            # Add star for primary source
            if obj.primary_source == 'woo':
                tag_style += "border: 2px solid gold;"
            sources_html.append(f'<span style="{tag_style}">WOO</span>')
        
        if obj.has_ghl:
            tag_style = "background-color: skyblue; color: white; padding: 3px 7px; border-radius: 10px; margin-right: 5px; display: inline-block;"
            # Add star for primary source
            if obj.primary_source == 'ghl':
                tag_style += "border: 2px solid gold;"
            sources_html.append(f'<span style="{tag_style}">GHL</span>')
        
        if not sources_html or obj.primary_source == 'crm':
            tag_style = "background-color: #999; color: white; padding: 3px 7px; border-radius: 10px; display: inline-block;"
            # Add star for primary source
            if obj.primary_source == 'crm':
                tag_style += "border: 2px solid gold;"
            sources_html.append(f'<span style="{tag_style}">CRM</span>')
        
        # Add multi-source indicator
        if obj.is_multi_source:
            return format_html('<span style="display: flex; align-items: center;"><span style="margin-right: 5px;">🔄</span>{}</span>', format_html(''.join(sources_html)))
        
        return format_html(''.join(sources_html))
    
    sources_display.short_description = 'Data Sources'
    sources_display.allow_tags = True
    
    def primary_source_display(self, obj):
        """Display primary source with a colored tag"""
        source_colors = {
            'woo': 'purple',
            'ghl': 'skyblue',
            'crm': '#999'
        }
        source_names = {
            'woo': 'WooCommerce',
            'ghl': 'GoHighLevel',
            'crm': 'CRM'
        }
        color = source_colors.get(obj.primary_source, '#999')
        name = source_names.get(obj.primary_source, 'Unknown')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 7px; '
            'border-radius: 10px; display: inline-block;">{}</span>',
            color, name
        )
    
    primary_source_display.short_description = 'Primary Source'
    primary_source_display.allow_tags = True

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'contact', 'woo_order_id', 'status', 'total_amount', 'created_at')
    search_fields = ('woo_order_id', 'contact__first_name', 'contact__last_name', 'contact__email')
    list_filter = ('status', 'created_at')
    readonly_fields = ('created_at', 'updated_at')

class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'woo_product_id', 'price', 'stock_status', 'created_at')
    search_fields = ('name',)
    list_filter = ('created_at', 'stock_status')
    readonly_fields = ('created_at', 'updated_at')

class OAuth2TokenAdmin(admin.ModelAdmin):
    list_display = ('location_id', 'token_status', 'expires_at', 'created_at', 'updated_at', 'connect_button', 'refresh_button', 'dashboard_link', 'view_details_button')
    readonly_fields = ('access_token', 'refresh_token', 'expires_at', 'created_at', 'updated_at')
    search_fields = ('location_id',)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_site.admin_view(self.ghl_dashboard_view), name='ghl_dashboard'),
            path('connect/', self.admin_site.admin_view(self.connect_view), name='connect_gohighlevel'),
            path('token/<uuid:token_id>/', self.admin_site.admin_view(self.token_detail_view), name='oauth_token_detail'),
            path('system-status/', self.admin_site.admin_view(self.system_status_view), name='system_status'),
        ]
        return custom_urls + urls
    
    def token_status(self, obj):
        if obj.is_expired:
            return format_html('<span style="color: red;">Expired</span>')
        return format_html('<span style="color: green;">Active</span>')
    
    token_status.short_description = "Status"
    
    def dashboard_link(self, obj=None):
        url = reverse('admin:ghl_dashboard')
        return format_html('<a href="{}">GoHighLevel Dashboard</a>', url)
    
    dashboard_link.short_description = "Dashboard"
    
    def view_details_button(self, obj):
        if obj:
            return format_html(
                '<a class="button" href="{}">View Details</a>',
                reverse('admin:oauth_token_detail', kwargs={'token_id': obj.id})
            )
        return ""
    
    view_details_button.short_description = "Details"
    
    def refresh_button(self, obj):
        if obj:
            return format_html(
                '<a class="button" href="{}">Refresh Token</a>',
                reverse('ghl_oauth_refresh', kwargs={'token_id': obj.id})
            )
        return ""
    
    refresh_button.short_description = "Refresh"

    def ghl_dashboard_view(self, request):
        tokens = OAuth2Token.objects.all().order_by('-updated_at')
        logs = TokenRequestLog.objects.all().order_by('-created_at')[:10]
        
        context = {
            'tokens': tokens,
            'logs': logs,
            **self.admin_site.each_context(request),
        }
        
        return render(request, 'admin/crm/ghl_dashboard.html', context)
    
    def token_detail_view(self, request, token_id):
        try:
            token = OAuth2Token.objects.get(id=token_id)
        except OAuth2Token.DoesNotExist:
            messages.error(request, "OAuth token not found.")
            return redirect('admin:ghl_dashboard')
        
        logs = TokenRequestLog.objects.filter(token=token).order_by('-created_at')[:10]
        
        context = {
            'token': token,
            'logs': logs,
            **self.admin_site.each_context(request),
        }
        
        return render(request, 'admin/crm/oauth_token_detail.html', context)

    def system_status_view(self, request):
        import psutil
        import datetime
        
        # Check if this is a diagnostic run request
        if request.method == 'POST' and 'run_diagnostics' in request.POST:
            return self.run_diagnostics(request)
        
        # Get OAuth token status
        tokens = OAuth2Token.objects.all()
        active_tokens = [token for token in tokens if not token.is_expired]
        has_active_tokens = len(active_tokens) > 0
        active_token_count = len(active_tokens)
        
        # Get system resource information
        disk = psutil.disk_usage('/')
        disk_space_total = f"{disk.total / (1024 * 1024 * 1024):.1f} GB"
        disk_space_used = f"{disk.used / (1024 * 1024 * 1024):.1f} GB"
        disk_space_percent = disk.percent
        disk_space_status = 'ok' if disk.percent < 70 else ('warning' if disk.percent < 90 else 'error')
        
        memory = psutil.virtual_memory()
        memory_total = f"{memory.total / (1024 * 1024 * 1024):.1f} GB"
        memory_used = f"{memory.used / (1024 * 1024 * 1024):.1f} GB"
        memory_percent = memory.percent
        memory_status = 'ok' if memory.percent < 70 else ('warning' if memory.percent < 90 else 'error')
        
        cpu_percent = psutil.cpu_percent(interval=0.5)
        cpu_status = 'ok' if cpu_percent < 70 else ('warning' if cpu_percent < 90 else 'error')
        
        # Get uptime
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time
        days, remainder = divmod(uptime.total_seconds(), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{int(days)} days, {int(hours)} hours, {int(minutes)} minutes"
        
        # Mock data for WooCommerce status and sync status (replace with actual implementation)
        woocommerce_status = 'connected'  # Example: 'connected', 'partial', 'disconnected'
        database_status = 'ok'  # Example: 'ok', 'error'
        last_sync_status = 'success'  # Example: 'success', 'in_progress', 'error', 'unknown'
        last_sync_time = datetime.datetime.now() - datetime.timedelta(hours=2)
        
        # Get system logs from the database
        system_logs = SystemLog.objects.all().order_by('-timestamp')[:10]
        
        # If no logs exist, create a sample log
        if not system_logs:
            from .utils import log_system_event
            log_system_event("System status dashboard viewed", "system", "info")
            log_system_event("Application started", "system", "success")
            system_logs = SystemLog.objects.all().order_by('-timestamp')[:10]
        
        context = {
            'has_active_tokens': has_active_tokens,
            'active_token_count': active_token_count,
            'woocommerce_status': woocommerce_status,
            'database_status': database_status,
            'last_sync_status': last_sync_status,
            'last_sync_time': last_sync_time,
            'disk_space_total': disk_space_total,
            'disk_space_used': disk_space_used,
            'disk_space_percent': disk_space_percent,
            'disk_space_status': disk_space_status,
            'memory_total': memory_total,
            'memory_used': memory_used,
            'memory_percent': memory_percent,
            'memory_status': memory_status,
            'cpu_percent': cpu_percent,
            'cpu_status': cpu_status,
            'uptime': uptime_str,
            'system_logs': system_logs,
            **self.admin_site.each_context(request),
        }
        
        return render(request, 'admin/crm/system_status.html', context)
        
    def run_diagnostics(self, request):
        """
        Run system diagnostics and return the results.
        """
        from .utils import log_system_event
        from django.db import connection
        import time
        
        log_system_event("System diagnostics started", "system", "in_progress")
        
        # Test database connection
        db_start_time = time.time()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            db_response_time = time.time() - db_start_time
            db_status = "success"
            log_system_event(
                f"Database connection test successful (response time: {db_response_time:.3f}s)",
                "system",
                "success"
            )
        except Exception as e:
            db_status = "error"
            log_system_event(
                f"Database connection test failed: {str(e)}",
                "system",
                "error",
                {"error": str(e)}
            )
        
        # Test OAuth token status
        try:
            tokens = OAuth2Token.objects.all()
            active_tokens = [token for token in tokens if not token.is_expired]
            expired_tokens = [token for token in tokens if token.is_expired]
            
            if active_tokens:
                log_system_event(
                    f"Found {len(active_tokens)} active OAuth tokens",
                    "oauth",
                    "success"
                )
            
            if expired_tokens:
                log_system_event(
                    f"Found {len(expired_tokens)} expired OAuth tokens that need refresh",
                    "oauth",
                    "warning"
                )
        except Exception as e:
            log_system_event(
                f"OAuth token check failed: {str(e)}",
                "system",
                "error",
                {"error": str(e)}
            )
        
        # Check system resources
        import psutil
        
        if psutil.virtual_memory().percent > 80:
            log_system_event(
                f"High memory usage detected: {psutil.virtual_memory().percent}%",
                "system",
                "warning"
            )
        
        if psutil.cpu_percent(interval=1) > 80:
            log_system_event(
                f"High CPU usage detected: {psutil.cpu_percent()}%",
                "system",
                "warning"
            )
        
        disk = psutil.disk_usage('/')
        if disk.percent > 80:
            log_system_event(
                f"High disk usage detected: {disk.percent}%",
                "system",
                "warning"
            )
        
        log_system_event("System diagnostics completed", "system", "success")
        
        messages.success(request, "System diagnostics completed successfully. Check the logs for details.")
        return redirect('admin:system_status')

    def connect_button(self, obj):
        if obj and obj.is_expired:
            return format_html(
                '<a class="button" href="{}">Reconnect</a>',
                get_authorization_url(obj.location_id)
            )
        elif not obj:
            return format_html(
                '<a class="button" href="{}">Connect</a>',
                reverse('admin:connect_gohighlevel')
            )
        return "Connected"
    
    connect_button.short_description = "Connection"
    
    def connect_view(self, request):
        # Default location ID - this could be made configurable
        location_id = request.GET.get('location_id', 'pgfekl6sKgofVPSuYOJo')
        return HttpResponseRedirect(get_authorization_url(location_id))

class TokenRequestLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'request_type', 'status', 'error_message_short', 'created_at')
    list_filter = ('request_type', 'status', 'created_at')
    readonly_fields = ('token', 'request_type', 'request_data', 'response_data', 'status', 'error_message', 'created_at')
    
    def error_message_short(self, obj):
        if obj.error_message and len(obj.error_message) > 50:
            return f"{obj.error_message[:50]}..."
        return obj.error_message
    
    error_message_short.short_description = 'Error'

class SystemLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'type', 'message', 'status')
    list_filter = ('type', 'status', 'timestamp')
    search_fields = ('message',)
    readonly_fields = ('timestamp',)
    
    def has_add_permission(self, request):
        # Only allow adding logs programmatically
        return False

class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'contact', 'start_time', 'end_time', 'status', 'provider', 'service', 'source']
    list_filter = ['status', 'source', 'provider', 'start_time']
    search_fields = ['title', 'notes', 'contact__first_name', 'contact__last_name', 'contact__email', 'provider', 'service']
    date_hierarchy = 'start_time'
    raw_id_fields = ['contact']

class AppointmentWebhookLogAdmin(admin.ModelAdmin):
    list_display = ['source', 'status', 'processed', 'created_at']
    list_filter = ['source', 'status', 'processed']
    readonly_fields = ['id', 'source', 'headers', 'payload', 'created_at']
    search_fields = ['source', 'error_message']
    date_hierarchy = 'created_at'

# Register models with the admin site
admin.site.register(Contact, ContactAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(OAuth2Token, OAuth2TokenAdmin)
admin.site.register(TokenRequestLog, TokenRequestLogAdmin)
admin.site.register(SystemLog, SystemLogAdmin)
admin.site.register(Appointment, AppointmentAdmin)
admin.site.register(AppointmentWebhookLog, AppointmentWebhookLogAdmin)

# Register with custom admin site
crm_admin_site.register(Contact, ContactAdmin)
crm_admin_site.register(Order, OrderAdmin)
crm_admin_site.register(Product, ProductAdmin)
crm_admin_site.register(OAuth2Token, OAuth2TokenAdmin)
crm_admin_site.register(TokenRequestLog, TokenRequestLogAdmin)
crm_admin_site.register(SystemLog, SystemLogAdmin)
crm_admin_site.register(Appointment, AppointmentAdmin)
crm_admin_site.register(AppointmentWebhookLog, AppointmentWebhookLogAdmin)
