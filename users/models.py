"""
Custom User Model for TeachLink
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.core.validators import MinLengthValidator
import uuid

class User(AbstractUser):
    """
    Custom user model supporting Teacher and Student roles
    """
    # Role choices
    class Role(models.TextChoices):
        TEACHER = 'TEACHER', 'Teacher'
        STUDENT = 'STUDENT', 'Student'
    
    # Override primary key to use UUID
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Core fields
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices)
    display_name = models.CharField(max_length=100)
    
    # Profile fields
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_activity = models.DateTimeField(default=timezone.now)
    
    # Account status
    is_active = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)
    
    # Use email as username field
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'display_name', 'role']
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return f"{self.display_name} ({self.get_role_display()})"
    
    def update_last_activity(self, ip_address=None):
        """Update user's last activity timestamp"""
        self.last_activity = timezone.now()
        if ip_address:
            self.last_login_ip = ip_address
        self.save(update_fields=['last_activity', 'last_login_ip'])
    
    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER
    
    @property
    def is_student(self):
        return self.role == self.Role.STUDENT


class UserSession(models.Model):
    """
    Track user sessions for engagement monitoring
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'user_sessions'
        indexes = [
            models.Index(fields=['user', '-last_activity']),
            models.Index(fields=['session_key']),
        ]
    
    def end_session(self):
        """Mark session as ended"""
        self.ended_at = timezone.now()
        self.save(update_fields=['ended_at'])
    
    @property
    def duration_seconds(self):
        if self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return (timezone.now() - self.started_at).total_seconds()