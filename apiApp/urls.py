# apiApp/urls.py
from django.urls import path
from . import views

app_name = 'apiApp'

urlpatterns = [
    path('', views.api_home, name='api_home'),
    path('pending-accounts/', views.pending_accounts_api, name='pending_accounts_api'),
    path('stage-executions/', views.stage_executions_api, name='stage_executions_api'),
]