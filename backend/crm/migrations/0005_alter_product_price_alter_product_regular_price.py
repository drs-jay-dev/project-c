# Generated by Django 4.2.7 on 2025-02-21 17:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0004_contact_woo_customer_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='product',
            name='regular_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
