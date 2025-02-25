import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doctorsstudio.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import IntegrityError

try:
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123456')
        print("Superuser created successfully")
    else:
        print("Superuser already exists")
except Exception as e:
    print(f"Error creating superuser: {str(e)}")
