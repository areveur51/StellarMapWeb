# StellarMapWeb/urls.py
from django.contrib import admin
from django.urls import path, include
from webApp.views import search_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apiApp.urls')),
    path('web/', include('webApp.urls')),
    path('tree/', include('radialTidyTreeApp.urls')),
    path('', search_view, name='home'),
]