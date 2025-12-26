from django.db import models
from django.conf import settings

class Room(models.Model):
    name = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(unique=True)
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='rooms')

    def __str__(self):
        return self.name

class Message(models.Model):
    room = models.ForeignKey(Room, related_name='messages', on_delete=models.CASCADE)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('audio', 'Audio'),
        ('image', 'Image'),
        ('call', 'Call'),
    ]
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    is_deleted_everyone = models.BooleanField(default=False)
    deleted_by = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='deleted_messages', blank=True)
    is_edited = models.BooleanField(default=False)
    
    # Call-specific fields (only used when message_type='call')
    call_duration = models.IntegerField(null=True, blank=True, help_text='Call duration in seconds')
    call_status = models.CharField(
        max_length=20, 
        choices=[
            ('missed', 'Missed'),
            ('answered', 'Answered'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        null=True,
        blank=True
    )



    class Meta:
        ordering = ('timestamp',)
    
    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"

class FriendRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]
    
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_requests', on_delete=models.CASCADE)
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='received_requests', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('from_user', 'to_user')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.from_user.username} -> {self.to_user.username} ({self.status})"

class BlockedUser(models.Model):
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='blocking', on_delete=models.CASCADE)
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='blocked_by', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('blocker', 'blocked')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.blocker.username} blocked {self.blocked.username}"
