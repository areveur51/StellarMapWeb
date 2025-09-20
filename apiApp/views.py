# apiApp/views.py
from django.http import HttpResponse

def api_home(request):
    """Simple API home view"""
    return HttpResponse("API is working!")

# Add your API views here as needed