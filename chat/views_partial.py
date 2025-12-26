class RoomMessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_slug):
        try:
            # Check if user is participant (optional security, but good)
            # For simplicity, assuming room_slug format user1_user2
            room = Room.objects.get(slug=room_slug)
            messages = Message.objects.filter(room=room)
            return Response(MessageSerializer(messages, many=True, context={'request': request}).data)
        except Room.DoesNotExist:
            return Response([])
