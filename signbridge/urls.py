"""
signbridge/urls.py — Root URL configuration for the SignBridge project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # API endpoints (provided by asl_app)
    path('api/', include('asl_app.urls', namespace='asl_app')),

    # Front-end: serve the single-page interface at the root
    path('', TemplateView.as_view(template_name='asl_app/index.html'), name='home'),
]

# Serve media & static files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
