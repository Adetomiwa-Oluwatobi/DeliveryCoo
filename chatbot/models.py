from django.db import models
from django.conf import settings

# Import your CustomUser from the order app
# Adjust the import path based on your app structure
try:
    from orders.models import CustomUser
except ImportError:
    # Fallback to using settings.AUTH_USER_MODEL
    CustomUser = settings.AUTH_USER_MODEL

class ChatSession(models.Model):
    # Use your CustomUser instead of Django's default User
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Optional: Add additional fields that might be useful
    is_active = models.BooleanField(default=True)
    title = models.CharField(max_length=200, blank=True, null=True)  # For naming chat sessions
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Chat Session'
        verbose_name_plural = 'Chat Sessions'
    
    def __str__(self):
        user_display = self.user.email if hasattr(self.user, 'email') else str(self.user)
        return f"Chat Session {self.session_id} - {user_display}"
    
    def get_last_message(self):
        """Get the last message in this session"""
        return self.messages.last()
    
    def message_count(self):
        """Get total number of messages in this session"""
        return self.messages.count()

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    message = models.TextField()
    is_user = models.BooleanField()  # True for user messages, False for bot responses
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Optional: Add additional fields for better functionality
    message_type = models.CharField(
        max_length=20, 
        choices=[
            ('text', 'Text'),
            ('image', 'Image'),
            ('file', 'File'),
            ('system', 'System Message'),
        ],
        default='text'
    )
    
    # For storing any metadata about the message
    metadata = models.JSONField(blank=True, null=True)
    
    class Meta:
        ordering = ['timestamp']
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'
    
    def __str__(self):
        sender = "User" if self.is_user else "Bot"
        user_display = self.session.user.email if hasattr(self.session.user, 'email') else str(self.session.user)
        return f"{sender} ({user_display}): {self.message[:50]}..."
    
    def get_sender_name(self):
        """Get a friendly name for the message sender"""
        if self.is_user:
            user = self.session.user
            if hasattr(user, 'first_name') and user.first_name:
                return f"{user.first_name} {user.last_name}".strip()
            elif hasattr(user, 'username'):
                return user.username
            elif hasattr(user, 'email'):
                return user.email
            else:
                return "User"
        else:
            return "Assistant"