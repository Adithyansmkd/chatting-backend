from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Max, Count, Case, When, IntegerField
from django.contrib.auth import get_user_model
from .models import Room, Message, FriendRequest
from accounts.serializers import UserSerializer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

User = get_user_model()

class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get list of conversations with last message, unread count, and timestamp
        """
        user = request.user
        
        # Get all rooms where user is a participant
        rooms = Room.objects.filter(participants=user)
        
        conversations = []
        
        for room in rooms:
            # Get the other participant (friend)
            other_user = room.participants.exclude(id=user.id).first()
            if not other_user:
                continue
            
            # Get last message in this room (excluding deleted messages)
            # Exclude messages deleted for everyone OR deleted by current user
            last_message = Message.objects.filter(
                room=room,
                is_deleted_everyone=False  # Not deleted for everyone
            ).exclude(
                deleted_by=user  # Not deleted by me
            ).order_by('-timestamp').first()
            
            if not last_message:
                continue  # Skip rooms with no messages
            
            # Count unread messages (messages sent by other user that current user hasn't read)
            # Also exclude deleted messages from unread count
            unread_count = Message.objects.filter(
                room=room,
                sender=other_user,
                is_read=False,
                is_deleted_everyone=False
            ).exclude(
                deleted_by=user
            ).count()
            
            # Build conversation data
            conversation = {
                'room_slug': room.slug,
                'friend': UserSerializer(other_user, context={'request': request}).data,
                'last_message': {
                    'id': last_message.id,  # Add message ID for filtering
                    'content': last_message.content,
                    'message_type': last_message.message_type,
                    'timestamp': last_message.timestamp,
                    'sender_id': last_message.sender.id,
                    'is_read': last_message.is_read,
                    'is_edited': last_message.is_edited,
                },
                'unread_count': unread_count,
            }
            
            conversations.append(conversation)
        
        # Sort by last message timestamp (most recent first)
        conversations.sort(key=lambda x: x['last_message']['timestamp'], reverse=True)
        
        return Response(conversations)


class MarkMessagesReadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, room_slug):
        """
        Mark all messages in a room as read for the current user
        """
        try:
            room = Room.objects.get(slug=room_slug, participants=request.user)
            
            # Mark all unread messages from other users as read
            Message.objects.filter(
                room=room,
                is_read=False
            ).exclude(
                sender=request.user
            ).update(is_read=True)
            
            # Broadcast read status
            channel_layer = get_channel_layer()
            room_group_name = f'chat_{room_slug}'
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'read_status_update',
                    'reader_id': request.user.id
                }
            )
            
            return Response({'message': 'Messages marked as read'})
        except Room.DoesNotExist:
            return Response({'error': 'Room not found'}, status=404)
