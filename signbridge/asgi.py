"""
ASGI config for SignBridge project.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'signbridge.settings')

application = get_asgi_application()
