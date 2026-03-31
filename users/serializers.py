from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import User, UserSession
import uuid

class UserSerializer(serializers.ModelSerializer):
    """Public user profile serializer"""
    class Meta:
        model = User
        fields = ['id', 'email', 'display_name', 'role', 'bio', 'avatar', 
                 'last_activity', 'date_joined']
        read_only_fields = ['id', 'last_activity', 'date_joined']

class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed user serializer for profile pages"""
    class Meta:
        model = User
        fields = ['id', 'email', 'display_name', 'role', 'bio', 'avatar',
                 'last_activity', 'date_joined', 'email_verified']
        read_only_fields = ['id', 'last_activity', 'date_joined', 'email_verified']

class RegisterSerializer(serializers.ModelSerializer):
    """User registration serializer"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = ['email', 'username', 'display_name', 'password', 
                 'password_confirm', 'role']
    
    def validate(self, attrs):
        """Validate that passwords match"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords do not match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            **validated_data,
            password=password
        )
        return user

class LoginSerializer(serializers.Serializer):
    """User login serializer"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """Validate login credentials"""
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(request=self.context.get('request'),
                              email=email, password=password)
            if not user:
                raise serializers.ValidationError("Invalid credentials")
            if not user.is_active:
                raise serializers.ValidationError("Account is disabled")
        else:
            raise serializers.ValidationError("Must include email and password")
        
        attrs['user'] = user
        return attrs

class UserSessionSerializer(serializers.ModelSerializer):
    """User session serializer"""
    class Meta:
        model = UserSession
        fields = ['id', 'ip_address', 'user_agent', 'started_at', 
                 'last_activity', 'ended_at', 'duration_seconds']
        read_only_fields = ['id', 'started_at', 'duration_seconds']