from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login
from django.utils import timezone
from django.db.models import Q
from .models import User, UserSession
from courses.models import Enrollment
from analytics.services.risk_engine import RiskEngine
from analytics.services.alert_generator import AlertGenerator
from .serializers import (
    UserSerializer, 
    UserDetailSerializer, 
    RegisterSerializer,
    LoginSerializer, 
    UserSessionSerializer
)

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing user profiles (read-only).
    """
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        """Use detail serializer for retrieve action"""
        if self.action == 'retrieve':
            return UserDetailSerializer
        return UserSerializer
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        user = self.request.user
        
        # Check if user is authenticated
        if not user.is_authenticated:
            return User.objects.none()
        
        # Teachers can view all active users
        if user.role == 'TEACHER':
            return User.objects.filter(is_active=True)
        
        # Students can only view teachers and themselves
        if user.role == 'STUDENT':
            return User.objects.filter(
                is_active=True
            ).filter(
                Q(role='TEACHER') | Q(id=user.id)
            )
        
        return User.objects.none()


class RegisterView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    API endpoint for user login.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        login(request, user)
        
        # Update last activity and IP
        ip_address = request.META.get('REMOTE_ADDR')
        user.update_last_activity(ip_address)
        
        # Create session record
        session = UserSession.objects.create(
            user=user,
            session_key=request.session.session_key,
            ip_address=ip_address,
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        if user.role == User.Role.STUDENT:
            enrollments = Enrollment.objects.filter(
                student=user,
                status=Enrollment.Status.ACTIVE
            )
            for enrollment in enrollments:
                enrollment.update_last_activity()
                RiskEngine.calculate_student_risk(str(enrollment.id))
                AlertGenerator.check_and_generate_alerts(enrollment_id=str(enrollment.id))
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'session_id': session.id
        })


class LogoutView(APIView):
    """
    API endpoint for user logout.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            # End current session
            session_key = request.session.session_key
            if session_key:
                UserSession.objects.filter(
                    user=request.user,
                    session_key=session_key,
                    ended_at__isnull=True
                ).update(ended_at=timezone.now())
            
            # Blacklist token
            refresh_token = request.data.get('refresh')
            if refresh_token:
                try:
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                except:
                    pass
            
            request.session.flush()
            
            return Response({'detail': 'Successfully logged out'})
        except:
            return Response(
                {'detail': 'Error during logout'},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for getting/updating the current user's profile.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserDetailSerializer
    
    def get_object(self):
        """Return the current authenticated user"""
        return self.request.user
    
    def perform_update(self, serializer):
        """Update user profile"""
        serializer.save()


class UserSessionsView(generics.ListAPIView):
    """
    API endpoint for viewing user's active sessions.
    """
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Return user's active sessions"""
        return UserSession.objects.filter(
            user=self.request.user
        ).order_by('-last_activity')


class ChangePasswordView(APIView):
    """
    API endpoint for changing password.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        if not user.check_password(old_password):
            return Response(
                {'old_password': 'Wrong password'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if new_password != confirm_password:
            return Response(
                {'new_password': 'Passwords do not match'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(new_password)
        user.save()
        
        # Logout other sessions
        UserSession.objects.filter(
            user=user,
            ended_at__isnull=True
        ).exclude(
            session_key=request.session.session_key
        ).update(ended_at=timezone.now())
        
        return Response({'detail': 'Password updated successfully'})
