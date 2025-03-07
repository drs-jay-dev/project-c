# Generated by Django 4.2.7 on 2025-03-05 18:13

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0007_systemlog_alter_contact_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='oauth2token',
            name='location_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.CreateModel(
            name='SyncState',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('sync_type', models.CharField(choices=[('ghl_contacts', 'GoHighLevel Contacts'), ('woo_customers', 'WooCommerce Customers'), ('woo_products', 'WooCommerce Products'), ('woo_orders', 'WooCommerce Orders')], max_length=20)),
                ('location_id', models.CharField(blank=True, max_length=100)),
                ('last_page_processed', models.IntegerField(default=0)),
                ('total_pages', models.IntegerField(blank=True, null=True)),
                ('success_count', models.IntegerField(default=0)),
                ('error_count', models.IntegerField(default=0)),
                ('last_sync_time', models.DateTimeField(blank=True, null=True)),
                ('is_complete', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name': 'Sync State',
                'verbose_name_plural': 'Sync States',
                'unique_together': {('sync_type', 'location_id')},
            },
        ),
    ]
