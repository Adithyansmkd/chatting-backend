from django.urls import path
from . import views
from . import views_upload
from .views_conversations import ConversationListView, MarkMessagesReadView

urlpatterns = [
    # Friend Requests
    path('friend-request/send/', views.SendFriendRequestView.as_view(), name='send_friend_request'),
    path('friend-request/<int:request_id>/accept/', views.AcceptFriendRequestView.as_view(), name='accept_friend_request'),
    path('friend-request/<int:request_id>/reject/', views.RejectFriendRequestView.as_view(), name='reject_friend_request'),
    path('friend-requests/', views.FriendRequestListView.as_view(), name='friend_requests'),
    path('friends/', views.FriendsListView.as_view(), name='friends_list'),
    
    # Blocking
    path('block/<int:user_id>/', views.BlockUserView.as_view(), name='block_user'),
    path('unblock/<int:user_id>/', views.UnblockUserView.as_view(), name='unblock_user'),
    path('blocked/', views.BlockedUsersListView.as_view(), name='blocked_users'),
    
    # Conversations
    path('conversations/', ConversationListView.as_view(), name='conversations'),
    path('conversations/<slug:room_slug>/mark-read/', MarkMessagesReadView.as_view(), name='mark_messages_read'),
    
    # Message History
    # Message History
    path('messages/<slug:room_slug>/', views.RoomMessageListView.as_view(), name='room_messages'),
    
    # Media Upload
    # Media Upload
    path('upload/audio/', views_upload.AudioUploadView.as_view(), name='audio_upload'),
]
