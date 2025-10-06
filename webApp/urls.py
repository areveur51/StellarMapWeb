# webApp/urls.py
from django.urls import path
from webApp import views

app_name = 'webApp'
urlpatterns = [
# Root redirect removed - now handled at main project level
    path('search/', views.search_view, name='search_view'),  # Search endpoint
    path('api/pending-accounts/', views.pending_accounts_api, name='pending_accounts_api'),  # API endpoint for auto-refresh
]
