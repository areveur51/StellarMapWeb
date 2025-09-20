# apiApp/urls.py
from django.urls import path
from . import views

app_name = 'apiApp'

urlpatterns = [
    path('', views.api_home, name='api_home'),
    # Add your API routes here as needed
]