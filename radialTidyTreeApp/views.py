# radialTidyTreeApp/views.py
from django.http import HttpResponse

def radial_tidy_tree_view(request):
    """Simple radial tree view"""
    return HttpResponse("<h1>Radial Tidy Tree</h1><p>This will display your radial tidy tree visualization.</p>")

# Add your radial tree views here as needed