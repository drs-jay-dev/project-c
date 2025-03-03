from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'contacts', views.ContactViewSet, basename='contact')
router.register(r'orders', views.OrderViewSet, basename='order')
router.register(r'products', views.ProductViewSet, basename='product')

urlpatterns = [
    path('', include(router.urls)),
    path('sync/', views.sync_woocommerce_data, name='sync_woocommerce_data'),
    path('sync/status/', views.get_sync_status, name='get_sync_status'),
    path('sync/stop/', views.stop_sync, name='stop_sync'),
]
