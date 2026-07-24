# StellarMapWeb/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from webApp.views import index_view, search_view, dashboard_view
from apiApp.views import health_check
from apiApp import auth_views

urlpatterns = [
    # Manager auth (Tailscale QR) — public search does not use these
    path('login/', auth_views.login_page, name='manager_login'),
    path('login/qr', auth_views.login_qr_page, name='manager_login_qr'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('api/auth/status', auth_views.auth_status, name='auth_status'),
    path('api/auth/qr/start', auth_views.qr_start, name='auth_qr_start'),
    path('api/auth/qr/status', auth_views.qr_status, name='auth_qr_status'),
    path('api/auth/qr/info', auth_views.qr_info, name='auth_qr_info'),
    path('api/auth/qr/approve', auth_views.qr_approve, name='auth_qr_approve'),
    path('api/auth/qr/complete', auth_views.qr_complete, name='auth_qr_complete'),
    path('api/auth/tailscale/direct', auth_views.tailscale_direct, name='auth_ts_direct'),

    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),
    path('api/', include('apiApp.urls')),
    path('web/', include('webApp.urls')),
    path('tree/', include('radialTidyTreeApp.urls')),
    path('', index_view, name='home'),
    re_path(r'^search/?$', search_view, name='search'),
    path('dashboard/', dashboard_view, name='dashboard'),
]

# Serve static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)