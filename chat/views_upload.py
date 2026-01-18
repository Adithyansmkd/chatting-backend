from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os
import time

class AudioUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        audio_file = request.FILES.get('audio')
        if not audio_file:
            return Response({'error': 'No audio file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate a unique filename
        ext = os.path.splitext(audio_file.name)[1]
        if not ext:
            ext = '.m4a' # Default for Flutter Sound
            
        filename = f"voice_notes/audio_{int(time.time())}_{request.user.id}{ext}"
        
        # Save file
        path = default_storage.save(filename, ContentFile(audio_file.read()))
        
        # Get URL
        # Assuming MEDIA_URL is configured
        file_url = request.build_absolute_uri(default_storage.url(path))
        
        return Response({
            'url': file_url,
            'path': path
        })
