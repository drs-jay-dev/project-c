from django.db import models
import uuid
from django.utils import timezone
import datetime

# Create your models here.

class Contact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    woo_customer_id = models.IntegerField(unique=True, null=True, blank=True)
    ghl_contact_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=100, blank=True, default='')
    last_name = models.CharField(max_length=100, blank=True, default='')
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    normalized_phone = models.CharField(max_length=50, null=True, blank=True)
    billing_address = models.TextField(blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_state = models.CharField(max_length=100, blank=True)
    billing_postcode = models.CharField(max_length=20, blank=True)
    primary_source = models.CharField(max_length=20, choices=[
        ('woo', 'WooCommerce'),
        ('ghl', 'GoHighLevel'),
        ('crm', 'CRM')
    ], default='crm')
    woo_data = models.JSONField(null=True, blank=True)
    ghl_data = models.JSONField(null=True, blank=True)
    ghl_tags = models.JSONField(default=list, blank=True)
    ghl_custom_fields = models.JSONField(default=list, blank=True)
    woo_last_sync = models.DateTimeField(null=True, blank=True)
    ghl_last_sync = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
        
    @property
    def has_woo(self):
        return self.woo_customer_id is not None
        
    @property
    def has_ghl(self):
        return self.ghl_contact_id is not None

    @property
    def sources_display(self):
        """Display a formatted list of data sources for this contact."""
        sources = []
        if self.has_woo:
            sources.append(f"WooCommerce (ID: {self.woo_customer_id})")
        if self.has_ghl:
            sources.append(f"GoHighLevel (ID: {self.ghl_contact_id})")
        if not sources:
            sources.append("CRM Only")
        return ", ".join(sources)

    class Meta:
        ordering = ['-created_at']

class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='orders')
    woo_order_id = models.CharField(max_length=100)
    order_date = models.DateTimeField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.woo_order_id} - {self.contact}"

class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    woo_product_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    regular_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20)
    stock_status = models.CharField(max_length=20)
    stock_quantity = models.IntegerField(null=True, blank=True)
    categories = models.JSONField(default=list)
    images = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']

class OAuth2Token(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location_id = models.CharField(max_length=100, unique=True)
    location_name = models.CharField(max_length=255, blank=True)
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Token for {self.location_name or self.location_id}"
    
    @property
    def is_expired(self):
        # Add a 5-minute buffer to ensure we refresh before actual expiration
        buffer = datetime.timedelta(minutes=5)
        return timezone.now() + buffer >= self.expires_at

class TokenRequestLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.ForeignKey(OAuth2Token, on_delete=models.CASCADE, related_name='logs', null=True, blank=True)
    request_type = models.CharField(max_length=20, choices=[
        ('auth', 'Authorization'),
        ('refresh', 'Refresh'),
        ('revoke', 'Revoke')
    ])
    status = models.CharField(max_length=20, choices=[
        ('success', 'Success'),
        ('error', 'Error')
    ])
    error_message = models.TextField(blank=True)
    request_data = models.JSONField(null=True, blank=True)
    response_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.request_type} - {self.status} - {self.created_at}"

    class Meta:
        ordering = ['-created_at']

class SystemLog(models.Model):
    """
    Model to store system logs and events for monitoring and troubleshooting.
    """
    TYPES = (
        ('oauth', 'OAuth'),
        ('sync', 'Synchronization'),
        ('system', 'System'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Information'),
    )
    
    STATUS = (
        ('success', 'Success'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Information'),
        ('in_progress', 'In Progress'),
    )
    
    timestamp = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=20, choices=TYPES)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS, default='info')
    details = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'System Log'
        verbose_name_plural = 'System Logs'
    
    def __str__(self):
        return f"{self.get_type_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

class SyncState(models.Model):
    """
    Model to store the state of sync operations for resuming interrupted syncs
    """
    SYNC_TYPES = (
        ('ghl_contacts', 'GoHighLevel Contacts'),
        ('woo_customers', 'WooCommerce Customers'),
        ('woo_products', 'WooCommerce Products'),
        ('woo_orders', 'WooCommerce Orders'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES)
    location_id = models.CharField(max_length=100, blank=True)  # For GHL syncs
    last_page_processed = models.IntegerField(default=0)
    total_pages = models.IntegerField(null=True, blank=True)
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    last_sync_time = models.DateTimeField(null=True, blank=True)
    is_complete = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('sync_type', 'location_id')
        verbose_name = 'Sync State'
        verbose_name_plural = 'Sync States'
    
    def __str__(self):
        return f"{self.get_sync_type_display()} - {self.last_sync_time}"

class Appointment(models.Model):
    """
    Model to store appointment data received from webhooks.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.CharField(max_length=100, blank=True, null=True)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='appointments', null=True, blank=True)
    title = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=50, default='scheduled')
    notes = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=100, blank=True)
    service = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=50, default='webhook')
    raw_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        ordering = ['-start_time']
        verbose_name = 'Appointment'
        verbose_name_plural = 'Appointments'

class AppointmentWebhookLog(models.Model):
    """
    Model to log webhook requests for appointments.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=50)
    headers = models.JSONField()
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=[
        ('success', 'Success'),
        ('error', 'Error'),
        ('pending', 'Pending'),
    ], default='pending')
    error_message = models.TextField(blank=True)
    processed = models.BooleanField(default=False)
    created_appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Webhook {self.source} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Appointment Webhook Log'
        verbose_name_plural = 'Appointment Webhook Logs'
