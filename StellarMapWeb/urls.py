# StellarMapWeb/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from webApp.views import index_view, search_view
from apiApp.views import health_check

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),
    path('api/', include('apiApp.urls')),
    path('web/', include('webApp.urls')),
    path('tree/', include('radialTidyTreeApp.urls')),
    path('', index_view, name='home'),
    re_path(r'^search/?$', search_view, name='search'),
]

# Serve static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)