# webApp/urls.py
from django.urls import path
from webApp import views

app_name = 'webApp'
urlpatterns = [
# Root redirect removed - now handled at main project level
    path('search/', views.search_view, name='search_view'),  # Search endpoint
    path('dashboard/', views.dashboard_view, name='dashboard_view'),  # Dashboard endpoint
    path('theme-test/', views.theme_test_view, name='theme_test'),  # Theme testing page
]
