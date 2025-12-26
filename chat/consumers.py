import json
import base64
from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Room, Message
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = 'chat_%s' % self.room_name

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        
        if self.scope['user'].is_authenticated:
            await self.update_user_status(True)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'user_id': self.scope['user'].id,
                    'status': 'online'
                }
            )

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        if self.scope['user'].is_authenticated:
            await self.update_user_status(False)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'user_id': self.scope['user'].id,
                    'status': 'offline',
                    'last_seen': timezone.now().isoformat()
                }
            )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        
        # Check if this is a special event type
        event_type = text_data_json.get('type', 'chat_message')
        
        if event_type == 'edit_message':
            await self.handle_edit_message(text_data_json)
            return

        if event_type == 'typing':
             sender_id = text_data_json.get('sender_id')
             if self.scope['user'].is_authenticated:
                 sender_id = self.scope['user'].id
                 
             await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_status',
                    'sender_id': sender_id,
                    'is_typing': text_data_json.get('is_typing', True)
                }
            )
             return

        if event_type == 'delete_message':
            await self.handle_delete_message(text_data_json)
            return

        if event_type == 'delete_message':
            await self.handle_delete_message(text_data_json)
            return

        # ==========================================
        # WebRTC Signaling Events
        # ==========================================
        if event_type in ['call_offer', 'call_answer', 'ice_candidate', 'call_end', 'call_rejected']:
            # Relay these messages directly to the room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'webrtc_signal',
                    'signal_type': event_type,
                    'sender_id': self.scope['user'].id if self.scope['user'].is_authenticated else None,
                    'payload': text_data_json.get('payload', {})
                }
            )
            return

        # Default: Chat Message
        message = text_data_json.get('message', '')
        message_type = text_data_json.get('message_type', 'text')
        sender_id = text_data_json.get('sender_id')
        
        # Fallback to scope user if available
        if self.scope['user'].is_authenticated:
            user = self.scope['user']
            sender_id = user.id
        else:
            try:
                user = await database_sync_to_async(User.objects.get)(id=sender_id)
            except User.DoesNotExist:
                user = None

        msg_obj = None
        if user and message:
            msg_obj = await self.save_message(user, message, message_type)

        if msg_obj:
            timestamp = msg_obj.timestamp.isoformat()
            # Notify for Global Updates (Home Screen)
            await self.notify_participants(msg_obj)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'message_type': message_type,
                'sender_id': sender_id,
                'timestamp': timestamp,
                'id': msg_obj.id if msg_obj else None,
                'is_read': False
            }
        )

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'message_type': event.get('message_type', 'text'),
            'sender_id': event['sender_id'],
            'timestamp': event.get('timestamp'),
            'id': event.get('id'),
            'is_read': event.get('is_read', False),
            'call_status': event.get('call_status'),  # Preserve status
            'call_duration': event.get('call_duration'), # Preserve duration
        }))

    async def user_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'user_id': event['user_id'],
            'status': event['status'],
            'last_seen': event.get('last_seen')
        }))

    async def typing_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'sender_id': event['sender_id'],
            'is_typing': event['is_typing']
        }))

    async def read_status_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'reader_id': event['reader_id']
        }))

    async def user_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_update',
            'user_id': event['user_id'],
            'profile_picture': event['profile_picture']
        }))

    async def handle_delete_message(self, data):
        """Handle message deletion requests"""
        if not self.scope['user'].is_authenticated:
            print("Delete failed: User not authenticated")
            return

        message_ids = data.get('message_ids', [])
        delete_type = data.get('delete_type', 'me')
        user = self.scope['user']

        print(f"\n=== DELETE REQUEST ===")
        print(f"User: {user.username} (ID: {user.id})")
        print(f"Message IDs: {message_ids}")
        print(f"Delete Type: {delete_type}")

        deleted_ids = await self.process_delete_messages(user, message_ids, delete_type)
        
        print(f"Successfully deleted IDs: {deleted_ids}")
        print(f"======================\n")
        
        if deleted_ids:
            if delete_type == 'everyone':
                # Broadcast to all users in the room
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'message_deleted',
                        'message_ids': deleted_ids,
                        'delete_type': 'everyone'
                    }
                )
            else:
                # Send only to the requesting user
                await self.send(text_data=json.dumps({
                    'type': 'message_deleted',
                    'message_ids': deleted_ids,
                    'delete_type': 'me'
                }))

    async def message_deleted(self, event):
        """Broadcast message deletion to clients"""
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'message_ids': event['message_ids'],
            'delete_type': event['delete_type']
        }))

    @database_sync_to_async
    def process_delete_messages(self, user, message_ids, delete_type):
        """Process message deletion in database"""
        from django.db import transaction
        
        deleted_ids = []
        
        try:
            # Convert all IDs to integers
            clean_ids = []
            for msg_id in message_ids:
                try:
                    clean_id = int(msg_id)
                    if clean_id > 0:  # Only process positive IDs (real database IDs)
                        clean_ids.append(clean_id)
                except (ValueError, TypeError):
                    print(f"Invalid ID: {msg_id}")
                    continue
            
            if not clean_ids:
                print("No valid IDs to delete")
                return []
            
            print(f"Clean IDs to process: {clean_ids}")
            
            with transaction.atomic():
                messages = Message.objects.filter(id__in=clean_ids)
                print(f"Found {messages.count()} messages in database")
                
                for msg in messages:
                    if delete_type == 'everyone':
                        # Check ownership and time limit (15 minutes)
                        time_diff = timezone.now() - msg.timestamp
                        seconds = time_diff.total_seconds()
                        is_owner = (msg.sender.id == user.id)
                        
                        print(f"Message {msg.id}: Owner={is_owner}, Age={seconds}s")
                        
                        if is_owner and seconds <= 900:  # 15 minutes
                            # HARD DELETE from database
                            msg_id = msg.id
                            msg.delete()
                            deleted_ids.append(msg_id)
                            print(f"DELETED message {msg_id} from database")
                        else:
                            print(f"Cannot delete message {msg.id}: Owner={is_owner}, TimeOK={seconds <= 900}")
                            
                    elif delete_type == 'me':
                        # Soft delete: add user to deleted_by
                        msg.deleted_by.add(user)
                        deleted_ids.append(msg.id)
                        print(f"Soft deleted message {msg.id} for user {user.username}")
                        
        except Exception as e:
            import traceback
            print(f"ERROR in process_delete_messages: {e}")
            print(traceback.format_exc())
            return []
        
        return deleted_ids

    @database_sync_to_async
    def save_message(self, user, message, message_type='text'):
        try:
            # Create room if it doesn't exist
            room, created = Room.objects.get_or_create(
                slug=self.room_name,
                defaults={'name': self.room_name}
            )
            
            # Add user as participant if not already added
            if not room.participants.filter(id=user.id).exists():
                room.participants.add(user)
            
            # Extract other user ID from room name (format: user1_user2)
            if created:
                try:
                    user_ids = self.room_name.split('_')
                    for uid in user_ids:
                        try:
                            other_user = User.objects.get(id=int(uid))
                            if other_user.id != user.id:
                                room.participants.add(other_user)
                        except (User.DoesNotExist, ValueError):
                            pass
                except:
                    pass
            
            # Create message
            msg = Message.objects.create(
                room=room,
                sender=user,
                content=message,
                message_type=message_type
            )
            return msg
        except Exception as e:
            print(f"Error saving message: {e}")
            return None

    @database_sync_to_async
    def update_user_status(self, is_online):
        if self.scope['user'].is_authenticated:
            user = self.scope['user']
            user.is_online = is_online
            if not is_online:
                user.last_seen = timezone.now()
            user.save()
    async def handle_edit_message(self, data):
        message_id = data.get('message_id')
        new_content_encoded = data.get('new_content')
        
        if not message_id or not new_content_encoded:
            return

        try:
            # Decode content
            new_content_bytes = base64.b64decode(new_content_encoded)
            new_content = new_content_bytes.decode('utf-8')
            
            # Get message and verify ownership
            # Use filter().first() to avoid exceptions
            message = await database_sync_to_async(lambda: Message.objects.filter(id=message_id).first())()
            
            if not message:
                return
                
            if self.scope['user'].is_authenticated:
                if message.sender_id != self.scope['user'].id:
                    return # Not sender
            else:
                 return # Guest? Should be authenticated
            
            # Check time limit (15 mins)
            age = timezone.now() - message.timestamp
            if age.total_seconds() > 900:
                return # Too old
                
            # Update
            message.content = new_content
            message.is_edited = True
            await database_sync_to_async(message.save)()
            
            # Broadcast
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_edited',
                    'message_id': message_id,
                    'new_content': new_content_encoded, # Send back encoded to keep format consistent
                }
            )
            
        except Exception as e:
            print(f"Error editing message: {e}")

    async def message_edited(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_edited',
            'message_id': event['message_id'],
            'new_content': event['new_content'],
        }))

    async def webrtc_signal(self, event):
        """
        Receive WebRTC signal from room group and send to over WebSocket.
        Don't send back to sender!
        """
        sender_id = event['sender_id']
        current_user_id = self.scope['user'].id if self.scope['user'].is_authenticated else None

        # Do not send the signal back to the sender
        if sender_id and current_user_id and sender_id == current_user_id:
            return

        await self.send(text_data=json.dumps({
            'type': event['signal_type'], # e.g., 'call_offer'
            'sender_id': sender_id,
            'payload': event['payload']
        }))


    async def notify_participants(self, msg_obj):
        participants = await database_sync_to_async(lambda: list(msg_obj.room.participants.all()))()
        sender_id = await database_sync_to_async(lambda: msg_obj.sender.id)()
        
        for p in participants:
            if p.id != sender_id:
                # Send to their global notification channel
                await self.channel_layer.group_send(
                    f'user_{p.id}',
                    {
                        'type': 'chat_notification', # Handled by NotificationConsumer
                        'notification_type': 'new_message',
                        'payload': {
                            'room': self.room_name,
                            'message': msg_obj.content,
                            'message_type': msg_obj.message_type,
                            'sender_id': sender_id,
                            'timestamp': msg_obj.timestamp.isoformat(),
                        }
                    }
                )


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if not self.scope['user'].is_authenticated:
            await self.close()
            return

        self.user = self.scope['user']
        # distinct group for each user to receive personal notifications
        self.group_name = f'user_{self.user.id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if self.scope['user'].is_authenticated:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            # Target user to send notification to
            target_user_id = data.get('target_user_id') 

            if not target_user_id:
                return

            target_group = f'user_{target_user_id}'

            if message_type == 'call_invite':
                # Send invitation to target user
                await self.channel_layer.group_send(
                    target_group,
                    {
                        'type': 'call_notification',
                        'notification_type': 'call_invite',
                        'sender_id': self.user.id,
                        'sender_name': self.user.username,
                        'sender_avatar': self.user.profile_picture.url if self.user.profile_picture else None,
                        'payload': data.get('payload', {})
                    }
                )
            elif message_type == 'save_call_log':
                # Save call log as a message
                await self.save_call_log(data)
            elif message_type in ['call_accept', 'call_offer', 'call_answer', 'call_reject', 'ice_candidate', 'call_end', 'call_ringing']:
                # Forward ALL WebRTC signaling messages
                print(f"NotificationConsumer: Forwarding {message_type} from user {self.user.id} to user {target_user_id}")
                await self.channel_layer.group_send(
                    target_group,
                    {
                        'type': 'call_notification',
                        'notification_type': message_type,
                        'sender_id': self.user.id,
                        'payload': data.get('payload', {})
                    }
                )
        except Exception as e:
            print(f"Error in NotificationConsumer receive: {e}")
    
    @database_sync_to_async
    def save_call_log(self, data):
        from .models import Room, Message
        
        try:
            peer_id = data.get('payload', {}).get('peer_id')
            duration = data.get('payload', {}).get('duration', 0)
            status = data.get('payload', {}).get('status', 'missed')
            caller_id = data.get('payload', {}).get('caller_id')
            
            if not peer_id:
                return
            
            # Get or create room
            user_ids = sorted([self.user.id, peer_id])
            room_slug = f"{user_ids[0]}_{user_ids[1]}"
            
            room, _ = Room.objects.get_or_create(
                slug=room_slug,
                defaults={'name': room_slug}
            )
            
            # Add participants
            room.participants.add(self.user)
            room.participants.add(User.objects.get(id=peer_id))
            
            # Create call message
            message = Message.objects.create(
                room=room,
                sender_id=caller_id,
                content='',  # Empty for call messages
                message_type='call',
                call_duration=duration,
                call_status=status
            )
            
            # Serialize for broadcast
            from .serializers import MessageSerializer
            # We can't use serializer easy in sync_to_async without more wrapping, so construct dict manually
            msg_data = {
                'id': message.id,
                'sender': message.sender.id,
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'message_type': 'call',
                'call_duration': duration,
                'call_status': status,
                'is_read': message.is_read
            }

            # Broadcast to room group (so ChatScreen receives it)
            channel_layer = self.channel_layer
            async_to_sync(channel_layer.group_send)(
                f"chat_{room_slug}", 
                {
                    'type': 'chat_message',
                    'message': message.content, # Content is empty but field required
                    'message_type': 'call',
                    'sender_id': message.sender.id,
                    'timestamp': message.timestamp.isoformat(),
                    'id': message.id,
                    'is_read': message.is_read,
                    'call_status': status,
                    'call_duration': duration,
                }
            )
            
            print(f"Call log saved and broadcast: {status}, duration: {duration}s")
        except Exception as e:
            print(f"Error saving call log: {e}")

    async def call_notification(self, event):
        await self.send(text_data=json.dumps(event))

    async def chat_notification(self, event):
        await self.send(text_data=json.dumps(event))

