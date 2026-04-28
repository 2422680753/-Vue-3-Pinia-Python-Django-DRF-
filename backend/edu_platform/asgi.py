"""
ASGI config for edu_platform project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edu_platform.settings')

django_asgi_app = get_asgi_application()

from apps.videos import routing as videos_routing
from apps.exams import routing as exams_routing

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(
            videos_routing.websocket_urlpatterns +
            exams_routing.websocket_urlpatterns
        )
    ),
})
