# webApp/urls.py
from django.urls import path
from webApp import views

app_name = 'webApp'
urlpatterns = [
    path('', views.redirect_to_search_view,
         name='redirect_to_search_view'),  # Root redirect
    path('search/', views.search_view, name='search_view'),  # Search endpoint
]
