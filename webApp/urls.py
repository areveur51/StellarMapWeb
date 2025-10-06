# webApp/urls.py
from django.urls import path
from webApp import views

app_name = 'webApp'
urlpatterns = [
# Root redirect removed - now handled at main project level
    path('search/', views.search_view, name='search_view'),  # Search endpoint
]
