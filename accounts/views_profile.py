from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model
from .serializers import UserSerializer
from django.core.files.storage import default_storage
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db.models import Q

User = get_user_model()


class GetProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current user's profile"""
        serializer = UserSerializer(request.user, context={'request': request})
        return Response(serializer.data)


class GetUserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        """Get specific user's public profile"""
        try:
            user = User.objects.get(id=user_id)
            serializer = UserSerializer(user, context={'request': request})
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Update display name and bio"""
        user = request.user
        
        display_name = request.data.get('display_name', '').strip()
        bio = request.data.get('bio', '').strip()
        
        # Validate display name
        if display_name and len(display_name) > 50:
            return Response(
                {'error': 'Display name must be 50 characters or less'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate bio
        if bio and len(bio) > 150:
            return Response(
                {'error': 'Bio must be 150 characters or less'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update fields
        if display_name is not None:
            user.display_name = display_name
        if bio is not None:
            user.bio = bio
        
        user.save()
        
        serializer = UserSerializer(user, context={'request': request})
        return Response(serializer.data)


class UpdateUsernameView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Change username with uniqueness validation"""
        user = request.user
        new_username = request.data.get('username', '').strip().lower()
        
        if not new_username:
            return Response(
                {'error': 'Username is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate username format
        if not new_username.replace('_', '').isalnum():
            return Response(
                {'error': 'Username can only contain letters, numbers, and underscores'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(new_username) < 3 or len(new_username) > 30:
            return Response(
                {'error': 'Username must be between 3 and 30 characters'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if username is already taken
        if User.objects.filter(username=new_username).exclude(id=user.id).exists():
            return Response(
                {'error': 'Username is already taken'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update username
        user.username = new_username
        user.save()
        
        serializer = UserSerializer(user, context={'request': request})
        return Response({
            'message': 'Username updated successfully',
            'user': serializer.data
        })


class CheckUsernameAvailabilityView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Check if username is available"""
        username = request.data.get('username', '').strip().lower()
        
        if not username:
            return Response({'available': False, 'error': 'Username is required'})
        
        # Check format
        if not username.replace('_', '').isalnum():
            return Response({'available': False, 'error': 'Invalid format'})
        
        if len(username) < 3 or len(username) > 30:
            return Response({'available': False, 'error': 'Invalid length'})
        
        # Check availability
        is_available = not User.objects.filter(username=username).exclude(id=request.user.id).exists()
        
        return Response({'available': is_available})


class UploadProfilePictureView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Upload or update profile picture"""
        user = request.user
        
        print(f"=== PROFILE PICTURE UPLOAD ===")
        print(f"User: {user.username}")
        print(f"FILES: {request.FILES}")
        print(f"DATA: {request.data}")
        print(f"Content-Type: {request.content_type}")
        
        if 'profile_picture' not in request.FILES:
            print("ERROR: No profile_picture in FILES")
            return Response(
                {'error': 'No image file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        image_file = request.FILES['profile_picture']
        print(f"Image file: {image_file.name}, Size: {image_file.size}, Type: {image_file.content_type}")
        
        # Validate file size (max 5MB)
        if image_file.size > 5 * 1024 * 1024:
            return Response(
                {'error': 'Image size must be less than 5MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if image_file.content_type not in allowed_types:
            print(f"ERROR: Invalid content type: {image_file.content_type}")
            return Response(
                {'error': f'Only JPEG, PNG, and WebP images are allowed. Got: {image_file.content_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Delete old profile picture if exists
        # if user.profile_picture:
        #     try:
        #         default_storage.delete(user.profile_picture.path)
        #     except:
        #         pass
        
        # Save new profile picture
        user.profile_picture = image_file
        user.save()
        
        print(f"SUCCESS: Profile picture saved")
        
        serializer = UserSerializer(user, context={'request': request})
        
        try:
            from chat.models import Conversation # Local import to avoid circular dependency
            channel_layer = get_channel_layer()
            conversations = Conversation.objects.filter(
                Q(initiator=user) | Q(receiver=user)
            )
            
            payload = {
                'type': 'user_update',
                'user_id': user.id,
                'profile_picture': serializer.data['profile_picture_url']
            }
            
            print(f"Broadcasting profile update to {conversations.count()} rooms")
            
            for conv in conversations:
                room_group_name = f'chat_{conv.room_name}'
                async_to_sync(channel_layer.group_send)(
                    room_group_name,
                    payload
                )
                
        except Exception as e:
            print(f"Broadcast Error: {e}")

        return Response({
            'message': 'Profile picture updated successfully',
            'user': serializer.data
        })


class DeleteProfilePictureView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Delete profile picture"""
        user = request.user
        
        if user.profile_picture:
            try:
                default_storage.delete(user.profile_picture.path)
            except:
                pass
            user.profile_picture = None
            user.save()
        
        serializer = UserSerializer(user, context={'request': request})
        return Response({
            'message': 'Profile picture deleted successfully',
            'user': serializer.data
        })
