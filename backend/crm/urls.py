from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from . import views
from . import ghl_oauth

router = DefaultRouter()
router.register(r'contacts', views.ContactViewSet, basename='contact')
router.register(r'orders', views.OrderViewSet, basename='order')
router.register(r'products', views.ProductViewSet, basename='product')

urlpatterns = [
    path('', include(router.urls)),
    path('sync/', views.sync_woocommerce_data, name='sync_woocommerce_data'),
    path('sync/status/', views.get_sync_status, name='get_sync_status'),
    path('sync/stop/', views.stop_sync, name='stop_sync'),
    path('sync/update-contact/', views.update_specific_contact, name='update_specific_contact'),
    path('sync/update-member-contacts/', views.update_member_contacts, name='update_member_contacts'),
    path('sync/update-contact-form/', views.update_contact_form, name='update_contact_form'),
    path('sync/update-member-contacts-form/', views.update_member_contacts_form, name='update_member_contacts_form'),
    path('contact-dashboard/', views.contact_dashboard, name='contact_dashboard'),
    # OAuth URLs
    path('oauth/authorize/', ghl_oauth.authorize_view, name='ghl_oauth_authorize'),
    path('oauth/callback/', ghl_oauth.oauth_callback, name='ghl_oauth_callback'),
    path('oauth/refresh/<uuid:token_id>/', ghl_oauth.refresh_token_view, name='ghl_oauth_refresh'),
    path('oauth/location/submit/', ghl_oauth.location_submit_view, name='ghl_oauth_location_submit'),
    path('sync/ghl/', views.sync_gohighlevel_data, name='sync_gohighlevel_data'),
    path('sync/ghl/status/', views.get_ghl_sync_status, name='get_ghl_sync_status'),
    path('dashboard/', views.ghl_dashboard_view, name='ghl_dashboard'),
    
    # New sync dashboard URLs
    path('sync/dashboard/', views.sync_dashboard, name='sync_dashboard'),
    path('sync/start/', views.start_sync, name='start_sync'),
    path('sync/view/<uuid:sync_id>/', views.sync_status_view, name='sync_status_view'),
    path('sync/cancel/<uuid:sync_id>/', views.cancel_sync, name='cancel_sync'),
    path('sync/detail/<uuid:sync_id>/', views.sync_detail_view, name='sync_detail_view'),
    
    # System status
    path('system/status/', views.system_status, name='system_status'),
]
