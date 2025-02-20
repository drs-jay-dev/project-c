from django.contrib import admin
from .models import Contact, Order

# Register your models here.

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phone', 'billing_city', 'billing_state')
    search_fields = ('first_name', 'last_name', 'email', 'phone', 'billing_city', 'billing_state')
    list_filter = ('billing_state', 'billing_city')
    ordering = ('last_name', 'first_name')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('woo_order_id', 'contact', 'order_date', 'total_amount', 'status')
    search_fields = ('woo_order_id', 'contact__email', 'contact__first_name', 'contact__last_name')
    list_filter = ('status', 'order_date')
