from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model
from chat.models import BlockedUser
from django.db.models import Q

User = get_user_model()

class BlockUserView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        target_id = request.data.get('user_id')
        
        if not target_id:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            target_user = User.objects.get(id=target_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
            
        if user.id == target_user.id:
            return Response({'error': 'You cannot block yourself'}, status=status.HTTP_400_BAD_REQUEST)
            
        BlockedUser.objects.get_or_create(blocker=user, blocked=target_user)
        
        return Response({'message': f'You have blocked {target_user.username}'})

class UnblockUserView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        target_id = request.data.get('user_id')
        
        if not target_id:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        BlockedUser.objects.filter(blocker=user, blocked__id=target_id).delete()
        
        return Response({'message': 'User unblocked successfully'})

class BlockStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, user_id):
        user = request.user
        
        is_blocked_by_me = BlockedUser.objects.filter(blocker=user, blocked__id=user_id).exists()
        is_blocked_by_them = BlockedUser.objects.filter(blocker__id=user_id, blocked=user).exists()
        
        return Response({
            'is_blocked_by_me': is_blocked_by_me,
            'is_blocked_by_them': is_blocked_by_them,
            'is_blocked': is_blocked_by_me or is_blocked_by_them
        })
