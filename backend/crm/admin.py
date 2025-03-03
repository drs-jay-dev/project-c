from django.contrib import admin
from .models import Contact, Order, Product, OAuth2Token, TokenRequestLog
from .admin_site import crm_admin_site
from django.utils.html import format_html
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

# Register your models here.

class HasWooFilter(admin.SimpleListFilter):
    """Filter contacts by WooCommerce integration status"""
    title = 'WooCommerce'
    parameter_name = 'has_woo'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Has WooCommerce'),
            ('no', 'No WooCommerce'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(woo_customer_id__isnull=True)
        if self.value() == 'no':
            return queryset.filter(woo_customer_id__isnull=True)

class HasGHLFilter(admin.SimpleListFilter):
    """Filter contacts by GoHighLevel integration status"""
    title = 'GoHighLevel'
    parameter_name = 'has_ghl'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Has GoHighLevel'),
            ('no', 'No GoHighLevel'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(ghl_contact_id__isnull=True)
        if self.value() == 'no':
            return queryset.filter(ghl_contact_id__isnull=True)

class CombinedSourceFilter(admin.SimpleListFilter):
    """Filter contacts by combined data sources"""
    title = 'Combined Sources'
    parameter_name = 'combined_source'
    
    def lookups(self, request, model_admin):
        return (
            ('woo_only', 'WooCommerce Only'),
            ('ghl_only', 'GoHighLevel Only'),
            ('woo_and_ghl', 'WooCommerce AND GoHighLevel'),
            ('crm_only', 'CRM Only (No Integrations)'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'woo_only':
            return queryset.filter(woo_customer_id__isnull=False, ghl_contact_id__isnull=True)
        if self.value() == 'ghl_only':
            return queryset.filter(ghl_contact_id__isnull=False, woo_customer_id__isnull=True)
        if self.value() == 'woo_and_ghl':
            return queryset.filter(woo_customer_id__isnull=False, ghl_contact_id__isnull=False)
        if self.value() == 'crm_only':
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
    
    list_display = ('full_name', 'email', 'phone', 'billing_city', 'billing_state', 
                   'sources_display')
    search_fields = ('first_name', 'last_name', 'email', 'phone', 'normalized_phone',
                    'billing_city', 'billing_state', 'ghl_contact_id')
    list_filter = (CombinedSourceFilter, HasWooFilter, HasGHLFilter)  
    ordering = ('last_name', 'first_name')
    readonly_fields = ('id', 'created_at', 'updated_at', 'normalized_phone', 'sources_display')
    
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
    list_display = ('woo_order_id', 'contact', 'order_date', 'total_amount', 'status')
    search_fields = ('woo_order_id', 'contact__email', 'contact__first_name', 'contact__last_name')
    list_filter = ('status', 'order_date')

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'woo_product_id', 'price', 'regular_price', 'stock_status', 'stock_quantity')
    search_fields = ('name', 'woo_product_id', 'description')
    list_filter = ('stock_status',)
    ordering = ('-created_at',)

class OAuth2TokenAdmin(admin.ModelAdmin):
    list_display = ('location_id', 'is_expired', 'created_at', 'updated_at')
    readonly_fields = ('id', 'created_at', 'updated_at', 'is_expired')
    search_fields = ('location_id',)
    list_filter = ('created_at', 'updated_at')
    
    def has_delete_permission(self, request, obj=None):
        return False

class TokenRequestLogAdmin(admin.ModelAdmin):
    list_display = ('request_type', 'status', 'token', 'created_at')
    list_filter = ('request_type', 'status', 'created_at')
    search_fields = ('token__location_id', 'error_message')
    readonly_fields = ('id', 'token', 'request_type', 'status', 'error_message', 
                      'request_data', 'response_data', 'created_at')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

# Register models with the custom admin site
crm_admin_site.register(Contact, ContactAdmin)
crm_admin_site.register(Order, OrderAdmin)
crm_admin_site.register(Product, ProductAdmin)
crm_admin_site.register(OAuth2Token, OAuth2TokenAdmin)
crm_admin_site.register(TokenRequestLog, TokenRequestLogAdmin)

# Also register with the default admin site for backward compatibility
admin.site.register(Contact, ContactAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(OAuth2Token, OAuth2TokenAdmin)
admin.site.register(TokenRequestLog, TokenRequestLogAdmin)
