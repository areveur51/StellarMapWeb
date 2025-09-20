# StellarMapWeb/urls.py
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

def home_view(request):
    """Simple home view"""
    return HttpResponse("""
    <h1>🌟 StellarMapWeb Django Application</h1>
    <p>Your Django project is running successfully!</p>
    <p>Available apps:</p>
    <ul>
        <li><strong>apiApp</strong> - API functionality</li>
        <li><strong>radialTidyTreeApp</strong> - Radial tidy tree features</li>
        <li><strong>webApp</strong> - General web interface</li>
    </ul>
    <p><a href="/admin/">Django Admin</a></p>
    """)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apiApp.urls')),
    path('web/', include('webApp.urls')),
    path('tree/', include('radialTidyTreeApp.urls')),
    path('', home_view, name='home'),
]