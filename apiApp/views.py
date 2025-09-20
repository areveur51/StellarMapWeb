# apiApp/views.py
from django.http import HttpResponse, JsonResponse

def api_home(request):
    """Simple API home view"""
    return JsonResponse({
        'message': 'StellarMapWeb API is working!',
        'status': 'success',
        'version': '1.0'
    })

# Add your API views here as needed