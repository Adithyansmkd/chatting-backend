from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from django.conf import settings
import uuid

User = get_user_model()

from .serializers import UserSerializer
from rest_framework_simplejwt.tokens import RefreshToken

class FirebaseSyncView(APIView):
    permission_classes = [] 

    def post(self, request):
        email = request.data.get('email')
        firebase_uid = request.data.get('uid')
        username = request.data.get('username')
        
        if not email or not firebase_uid:
            return Response({'error': 'Email and UID required'}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Try to find existing user
        user = User.objects.filter(email=email).first()

        # 2. If no user, create one
        if not user:
            if not username:
                username = email.split('@')[0]
            
            # Ensure unique username
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=str(uuid.uuid4()) # Unusable password
            )
        
        # 3. Generate JWT Token (Matching standard login)
        refresh = RefreshToken.for_user(user)

        # 4. Return Data with FULL User Serializer
        # This fixes "List<Object> is not subtype..." and "Sync Error" because
        # Flutter expects fields like 'chat_code' which UserSerializer provides.
        return Response({
            'token': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        })
