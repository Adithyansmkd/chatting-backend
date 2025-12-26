from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from urllib.parse import parse_qs

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token_string):
    """Get user from JWT token"""
    try:
        # Validate and decode the token
        access_token = AccessToken(token_string)
        user_id = access_token['user_id']
        
        # Get the user
        user = User.objects.get(id=user_id)
        return user
    except (InvalidToken, TokenError, User.DoesNotExist, KeyError) as e:
        print(f"Token authentication failed: {e}")
        return AnonymousUser()

class TokenAuthMiddleware:
    """
    Custom middleware to authenticate WebSocket connections using JWT tokens
    Token should be passed as query parameter: ws://...?token=xxx
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        # Get query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        
        # Extract token from query params
        token = query_params.get('token', [None])[0]
        
        if token:
            # Authenticate user with token
            scope['user'] = await get_user_from_token(token)
            print(f"WebSocket authenticated user: {scope['user']}")
        else:
            scope['user'] = AnonymousUser()
            print("WebSocket connection without token - anonymous user")
        
        return await self.app(scope, receive, send)

def TokenAuthMiddlewareStack(app):
    """
    Wrapper function to apply TokenAuthMiddleware
    """
    return TokenAuthMiddleware(app)
