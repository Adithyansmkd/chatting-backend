import os
from django.core.asgi import get_asgi_application

# Set Django settings module FIRST
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chattingarena.settings')

# Initialize Django BEFORE importing anything else
django_asgi_app = get_asgi_application()

# NOW import channels and custom middleware (after Django is initialized)
from channels.routing import ProtocolTypeRouter, URLRouter
from chat.middleware import TokenAuthMiddlewareStack
import chat.routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": TokenAuthMiddlewareStack(
        URLRouter(
            chat.routing.websocket_urlpatterns
        )
    ),
})
