from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.contrib.auth import get_user_model
from .models import FriendRequest, BlockedUser, Room, Message
from .serializers import FriendRequestSerializer, BlockedUserSerializer, RoomSerializer, MessageSerializer
from accounts.serializers import UserSerializer

User = get_user_model()

class SendFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        to_user_id = request.data.get('to_user_id')
        
        if not to_user_id:
            return Response({'error': 'to_user_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            to_user = User.objects.get(id=to_user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if to_user == request.user:
            return Response({'error': 'Cannot send friend request to yourself'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if blocked
        if BlockedUser.objects.filter(Q(blocker=request.user, blocked=to_user) | Q(blocker=to_user, blocked=request.user)).exists():
            return Response({'error': 'Cannot send friend request'}, status=status.HTTP_403_FORBIDDEN)
        
        # Check if request already exists
        if FriendRequest.objects.filter(from_user=request.user, to_user=to_user).exists():
            return Response({'error': 'Friend request already sent'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if reverse request exists (they sent you a request)
        reverse_request = FriendRequest.objects.filter(from_user=to_user, to_user=request.user, status='pending').first()
        if reverse_request:
            # Auto-accept both ways
            reverse_request.status = 'accepted'
            reverse_request.save()
            friend_request = FriendRequest.objects.create(from_user=request.user, to_user=to_user, status='accepted')
            return Response({'message': 'Friend request accepted automatically', 'friend_request': FriendRequestSerializer(friend_request, context={'request': request}).data}, status=status.HTTP_201_CREATED)
        
        friend_request = FriendRequest.objects.create(from_user=request.user, to_user=to_user)
        return Response(FriendRequestSerializer(friend_request, context={'request': request}).data, status=status.HTTP_201_CREATED)

class AcceptFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, request_id):
        try:
            friend_request = FriendRequest.objects.get(id=request_id, to_user=request.user, status='pending')
        except FriendRequest.DoesNotExist:
            return Response({'error': 'Friend request not found'}, status=status.HTTP_404_NOT_FOUND)
        
        friend_request.status = 'accepted'
        friend_request.save()
        
        # Create reverse friend request
        FriendRequest.objects.get_or_create(
            from_user=request.user,
            to_user=friend_request.from_user,
            defaults={'status': 'accepted'}
        )
        
        return Response(FriendRequestSerializer(friend_request, context={'request': request}).data)

class RejectFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, request_id):
        try:
            friend_request = FriendRequest.objects.get(id=request_id, to_user=request.user, status='pending')
        except FriendRequest.DoesNotExist:
            return Response({'error': 'Friend request not found'}, status=status.HTTP_404_NOT_FOUND)
        
        friend_request.status = 'rejected'
        friend_request.save()
        
        return Response(FriendRequestSerializer(friend_request, context={'request': request}).data)

class FriendRequestListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get pending requests received by the user
        requests = FriendRequest.objects.filter(to_user=request.user, status='pending')
        return Response(FriendRequestSerializer(requests, many=True, context={'request': request}).data)

class FriendsListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get accepted friend requests
        friend_requests = FriendRequest.objects.filter(
            Q(from_user=request.user, status='accepted') | Q(to_user=request.user, status='accepted')
        )
        
        # Extract unique friend user IDs
        friend_ids = set()
        for fr in friend_requests:
            if fr.from_user == request.user:
                friend_ids.add(fr.to_user.id)
            else:
                friend_ids.add(fr.from_user.id)
        
        friends = User.objects.filter(id__in=friend_ids)
        return Response(UserSerializer(friends, many=True, context={'request': request}).data)

class BlockUserView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, user_id):
        try:
            user_to_block = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if user_to_block == request.user:
            return Response({'error': 'Cannot block yourself'}, status=status.HTTP_400_BAD_REQUEST)
        
        blocked, created = BlockedUser.objects.get_or_create(blocker=request.user, blocked=user_to_block)
        
        # Delete any friend requests between them
        FriendRequest.objects.filter(
            Q(from_user=request.user, to_user=user_to_block) | Q(from_user=user_to_block, to_user=request.user)
        ).delete()
        
        return Response(BlockedUserSerializer(blocked, context={'request': request}).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

class UnblockUserView(APIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, user_id):
        try:
            blocked_user = BlockedUser.objects.get(blocker=request.user, blocked_id=user_id)
            blocked_user.delete()
            return Response({'message': 'User unblocked'}, status=status.HTTP_200_OK)
        except BlockedUser.DoesNotExist:
            return Response({'error': 'User not blocked'}, status=status.HTTP_404_NOT_FOUND)

class BlockedUsersListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        blocked_users = BlockedUser.objects.filter(blocker=request.user)
        return Response(BlockedUserSerializer(blocked_users, many=True, context={'request': request}).data)

class RoomMessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_slug):
        try:
            page = int(request.query_params.get('page', 1))
            page_size = 40
            start = (page - 1) * page_size
            end = page * page_size

            room = Room.objects.get(slug=room_slug)
            
            # Fetch messages ordered by newest first, then slice
            messages = Message.objects.filter(room=room).order_by('-timestamp')[start:end]
            
            # Reverse to return in chronological order (Oldest -> Newest)
            # This allows the frontend to simply append/prepend correctly
            messages_list = list(messages)[::-1]
            
            return Response(MessageSerializer(messages_list, many=True, context={'request': request}).data)
        except Room.DoesNotExist:
            return Response([])

import os
import uuid
from django.conf import settings
from django.core.files.storage import default_storage

class AudioUploadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        audio_file = request.FILES.get('audio')
        if not audio_file:
            return Response({'error': 'No audio file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate extension (optional but good practice)
        ext = os.path.splitext(audio_file.name)[1].lower()
        # Allow common audio types
        if ext not in ['.m4a', '.mp3', '.wav', '.aac', '.ogg']:
             return Response({'error': 'Invalid file format'}, status=status.HTTP_400_BAD_REQUEST)

        # Saves to MEDIA_ROOT/audio/<uuid><ext>
        filename = f"audio/{uuid.uuid4()}{ext}"
        saved_path = default_storage.save(filename, audio_file)
        
        # Build full URL
        # settings.MEDIA_URL is typically '/media/'
        # We want http://domain/media/audio/xyz.m4a
        file_url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)
        
        return Response({'url': file_url}, status=status.HTTP_201_CREATED)
