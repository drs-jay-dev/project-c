from rest_framework import serializers
from .models import Contact, Order, Product, Appointment, AppointmentWebhookLog

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)

    class Meta:
        model = Order
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'

class AppointmentSerializer(serializers.ModelSerializer):
    contact_name = serializers.SerializerMethodField()
    formatted_start_time = serializers.SerializerMethodField()
    formatted_end_time = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = '__all__'
    
    def get_contact_name(self, obj):
        if obj.contact:
            return f"{obj.contact.first_name} {obj.contact.last_name}".strip()
        return ""
    
    def get_formatted_start_time(self, obj):
        return obj.start_time.strftime('%Y-%m-%d %H:%M:%S')
    
    def get_formatted_end_time(self, obj):
        return obj.end_time.strftime('%Y-%m-%d %H:%M:%S')

class AppointmentWebhookLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppointmentWebhookLog
        fields = '__all__'
