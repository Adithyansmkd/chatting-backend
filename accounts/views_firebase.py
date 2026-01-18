from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from django.conf import settings
import uuid

User = get_user_model()

class FirebaseSyncView(APIView):
    permission_classes = [] # Allow anyone to call this (secured by Firebase UID logic ideally, but open for now)

    def post(self, request):
        email = request.data.get('email')
        firebase_uid = request.data.get('uid')
        username = request.data.get('username')
        
        if not email or not firebase_uid:
            return Response({'error': 'Email and UID required'}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Try to find existing user by email
        user = User.objects.filter(email=email).first()

        # 2. If no user, create one
        if not user:
            # If username not provided, generate one from email
            if not username:
                username = email.split('@')[0]
            
            # Ensure unique username
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            # Create user (Password is random since they use Firebase Auth)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=str(uuid.uuid4()) # Unusable password
            )
            # You might want to save firebase_uid in a profile model if needed
        
        # 3. Get or Create Token
        token, _ = Token.objects.get_or_create(user=user)

        # 4. Return Data
        return Response({
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'profile_picture': user.profile_picture.url if user.profile_picture else None,
                # Add other fields as needed matching existing UserSerializer
            }
        })
