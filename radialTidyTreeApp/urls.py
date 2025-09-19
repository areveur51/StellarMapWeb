# radialTidyTreeApp/urls.py
from django.urls import path
from radialTidyTreeApp.views import radial_tidy_tree_view

app_name = 'radialTidyTreeApp'
urlpatterns = [
    path('', radial_tidy_tree_view,
         name='radial_tidy_tree_view'),  # Simple root path for app
]
