# radialTidyTreeApp/urls.py
from django.urls import path
from . import views

app_name = 'radialTidyTreeApp'

urlpatterns = [
    path('', views.radial_tidy_tree_view, name='radial_tidy_tree'),
    path('radial-tree/', views.radial_tidy_tree_view, name='radial_tidy_tree_alt'),
]