# webApp/views.py
from django.shortcuts import render
from django.http import HttpResponse

def redirect_to_search_view(request):
    """Simple redirect view"""
    return HttpResponse("<h1>Welcome to StellarMapWeb!</h1><p>Your Django project is running successfully!</p>")

def search_view(request):
    """Simple search view"""
    return HttpResponse("<h1>Search</h1><p>This is the search page for your Stellar Map application.</p>")