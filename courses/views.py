"""
Course Management Views
"""
import logging

from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework_simplejwt.authentication import JWTAuthentication  # Make sure this is imported
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.db import models  # Add this import
from .models import Course, Module, Lesson, Enrollment, LessonCompletion, Competency, LessonCompetency, AttendanceRecord
from analytics.models import LessonInteraction, CompetencyPerformance
from analytics.services.risk_engine import RiskEngine
from analytics.services.alert_generator import AlertGenerator
from .serializers import (
    CourseSerializer, CourseDetailSerializer,
    ModuleSerializer, ModuleDetailSerializer,
    LessonSerializer, LessonDetailSerializer,
    EnrollmentSerializer, EnrollmentDetailSerializer,
    LessonCompletionSerializer,
    CompetencySerializer, LessonCompetencySerializer,
    AttendanceRecordSerializer
)
from users.permissions import IsTeacher, IsStudent, IsTeacherOrReadOnly

logger = logging.getLogger(__name__)


class CourseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Course operations
    """
    queryset = Course.objects.all()
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CourseDetailSerializer
        return CourseSerializer
    
    def get_queryset(self):
        queryset = Course.objects.all()
        user = self.request.user
        
        # Filter by status if teacher viewing own courses
        if user.is_authenticated and user.role == 'TEACHER':  # Changed from user.is_teacher
            if self.action == 'list':
                status_param = self.request.query_params.get('status', None)
                if status_param:
                    queryset = queryset.filter(
                        teacher=user,
                        status=status_param
                    )
                else:
                    queryset = queryset.filter(teacher=user)
        
        # If student, only show published courses
        elif user.is_authenticated and user.role == 'STUDENT':  # Changed from user.is_student
            queryset = queryset.filter(status=Course.Status.PUBLISHED)
            
            # Filter enrolled/unenrolled
            enrolled = self.request.query_params.get('enrolled', None)
            if enrolled is not None:
                if enrolled.lower() == 'true':
                    queryset = queryset.filter(
                        enrollments__student=user,
                        enrollments__status=Enrollment.Status.ACTIVE
                    )
                elif enrolled.lower() == 'false':
                    queryset = queryset.exclude(
                        enrollments__student=user,
                        enrollments__status=Enrollment.Status.ACTIVE
                    )

        # Add analytics preview fields for list views.
        if self.action == 'list':
            queryset = queryset.annotate(
                high_risk_count=models.Count(
                    'enrollments',
                    filter=models.Q(
                        enrollments__status=Enrollment.Status.ACTIVE,
                        enrollments__risk_level__in=['HIGH', 'CRITICAL'],
                    ),
                ),
                medium_risk_count=models.Count(
                    'enrollments',
                    filter=models.Q(
                        enrollments__status=Enrollment.Status.ACTIVE,
                        enrollments__risk_level='MEDIUM',
                    ),
                ),
                low_risk_count=models.Count(
                    'enrollments',
                    filter=models.Q(
                        enrollments__status=Enrollment.Status.ACTIVE,
                        enrollments__risk_level='LOW',
                    ),
                ),
                avg_progress=models.Avg(
                    'enrollments__progress_percentage',
                    filter=models.Q(enrollments__status=Enrollment.Status.ACTIVE),
                ),
                avg_quiz_score=models.Avg(
                    'enrollments__average_quiz_score',
                    filter=models.Q(enrollments__status=Enrollment.Status.ACTIVE),
                ),
            )
        
        return queryset
    
    def perform_create(self, serializer):
        """Set teacher as current user and email enrollment key."""
        course = serializer.save(teacher=self.request.user)
        self._send_enrollment_key_email(course, regenerated=False)

    def _generate_unique_course_key(self):
        """Generate a unique enrollment key."""
        key = get_random_string(8, allowed_chars='ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
        while Course.objects.filter(enrollment_key=key).exists():
            key = get_random_string(8, allowed_chars='ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
        return key

    def _send_enrollment_key_email(self, course, regenerated=False):
        """Email teacher the enrollment key for sharing with students."""
        teacher_email = getattr(course.teacher, 'email', None)
        if not teacher_email:
            return

        courses_url = self.request.build_absolute_uri(reverse('dashboard_courses'))
        subject = f"TeachLink enrollment key for {course.title}"
        if regenerated:
            intro = "A new enrollment key has been generated for your course."
        else:
            intro = "Your course was created successfully."

        message = (
            f"Hello {course.teacher.display_name},\n\n"
            f"{intro}\n\n"
            f"Course: {course.title}\n"
            f"Enrollment Key: {course.enrollment_key}\n\n"
            f"Share this key with students so they can enroll from their sidebar.\n"
            f"Manage course: {courses_url}\n\n"
            "TeachLink"
        )

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[teacher_email],
                fail_silently=False,
            )
        except Exception:
            logger.exception(
                "Failed sending enrollment key email for course %s to %s",
                course.id,
                teacher_email,
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsStudent])
    def enroll(self, request, pk=None):
        """Enroll current student in course"""
        course = self.get_object()
        student = request.user

        if course.status != Course.Status.PUBLISHED:
            return Response(
                {'error': 'This course is not open for enrollment yet'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already enrolled
        enrollment, created = Enrollment.objects.get_or_create(
            student=student,
            course=course,
            defaults={'status': Enrollment.Status.ACTIVE}
        )
        
        if created:
            return Response({
                'message': 'Successfully enrolled in course',
                'enrollment': EnrollmentSerializer(enrollment).data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'message': 'Already enrolled in this course',
                'enrollment': EnrollmentSerializer(enrollment).data
            }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsTeacher])
    def publish(self, request, pk=None):
        """Publish a teacher's course so students can enroll."""
        course = self.get_object()
        if course.teacher != request.user:
            self.permission_denied(request)
        course.status = Course.Status.PUBLISHED
        course.save(update_fields=['status'])
        return Response({
            'message': 'Course published successfully',
            'status': course.status
        })

    @action(detail=True, methods=['post'], permission_classes=[IsTeacher])
    def regenerate_enrollment_key(self, request, pk=None):
        """Regenerate enrollment key and email it to the teacher."""
        course = self.get_object()
        if course.teacher != request.user:
            self.permission_denied(request)

        course.enrollment_key = self._generate_unique_course_key()
        course.save(update_fields=['enrollment_key'])
        self._send_enrollment_key_email(course, regenerated=True)

        return Response({
            'message': 'Enrollment key regenerated and emailed',
            'enrollment_key': course.enrollment_key,
        })

    @action(detail=True, methods=['post'], permission_classes=[IsTeacher])
    def unpublish(self, request, pk=None):
        """Unpublish a teacher's course and move it back to draft."""
        course = self.get_object()
        if course.teacher != request.user:
            self.permission_denied(request)
        course.status = Course.Status.DRAFT
        course.save(update_fields=['status'])
        return Response({
            'message': 'Course unpublished successfully',
            'status': course.status
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsStudent])
    def unenroll(self, request, pk=None):
        """Unenroll from course"""
        course = self.get_object()
        student = request.user
        
        try:
            enrollment = Enrollment.objects.get(
                student=student,
                course=course,
                status=Enrollment.Status.ACTIVE
            )
            enrollment.status = Enrollment.Status.DROPPED
            enrollment.save()
            return Response({'message': 'Successfully unenrolled from course'})
        except Enrollment.DoesNotExist:
            return Response(
                {'error': 'Not enrolled in this course'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'], permission_classes=[IsTeacher])
    def students_progress(self, request, pk=None):
        """
        Get unified student progress view for a course.
        Endpoint: GET /api/courses/{id}/students_progress/
        Filters: ?risk_level=HIGH,MEDIUM,LOW | ?progress_min=0&progress_max=100 | ?last_activity_days=7
        """
        course = self.get_object()
        
        # Check permission
        if course.teacher != request.user:
            return Response(
                {'error': 'Only the course teacher can view student progress'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get all enrollments
        enrollments = Enrollment.objects.filter(
            course=course,
            status=Enrollment.Status.ACTIVE
        ).select_related('student')
        
        # Apply filters
        risk_levels = request.query_params.get('risk_level', '').split(',')
        risk_levels = [r.strip().upper() for r in risk_levels if r.strip()]
        if risk_levels:
            enrollments = enrollments.filter(risk_level__in=risk_levels)
        
        progress_min = request.query_params.get('progress_min')
        progress_max = request.query_params.get('progress_max')
        if progress_min:
            enrollments = enrollments.filter(progress_percentage__gte=float(progress_min))
        if progress_max:
            enrollments = enrollments.filter(progress_percentage__lte=float(progress_max))
        
        last_activity_days = request.query_params.get('last_activity_days')
        if last_activity_days:
            from django.utils import timezone
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=int(last_activity_days))
            enrollments = enrollments.filter(last_activity__gte=cutoff)
        
        # Sort
        sort_by = request.query_params.get('sort_by', '-progress_percentage')
        enrollments = enrollments.order_by(sort_by)
        
        # Build response
        students_data = []
        for enrollment in enrollments:
            students_data.append({
                'student_id': str(enrollment.student.id),
                'student_name': enrollment.student.display_name,
                'student_email': enrollment.student.email,
                'progress_percentage': float(enrollment.progress_percentage),
                'risk_level': enrollment.risk_level,
                'risk_score': float(enrollment.risk_score),
                'engagement_score': float(enrollment.engagement_score),
                'average_quiz_score': float(enrollment.average_quiz_score),
                'last_activity': enrollment.last_activity.isoformat(),
                'days_since_last_activity': enrollment.days_since_last_activity,
                'enrolled_at': enrollment.enrolled_at.isoformat(),
                'is_at_risk': enrollment.is_at_risk,
                'is_inactive': enrollment.is_inactive,
            })
        
        return Response({
            'course_id': str(course.id),
            'course_title': course.title,
            'total_students': len(students_data),
            'at_risk_count': sum(1 for s in students_data if s['is_at_risk']),
            'inactive_count': sum(1 for s in students_data if s['is_inactive']),
            'students': students_data
        }, status=status.HTTP_200_OK)


class ModuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Module operations
    """
    queryset = Module.objects.all()
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrReadOnly]
    serializer_class = ModuleSerializer
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ModuleDetailSerializer
        return ModuleSerializer
    
    def get_queryset(self):
        queryset = Module.objects.all()
        course_id = self.request.query_params.get('course', None)
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        return queryset.order_by('order')
    
    def perform_create(self, serializer):
        """Auto-set order if not provided"""
        course_id = self.request.data.get('course')
        course = get_object_or_404(Course, id=course_id)
        
        # Check if user is the course teacher
        if course.teacher != self.request.user:
            self.permission_denied(self.request)
        
        # Auto-increment order
        last_order = Module.objects.filter(course=course).aggregate(
            models.Max('order')
        )['order__max']
        
        order = self.request.data.get('order', (last_order or 0) + 1)
        serializer.save(course=course, order=order)


class LessonViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Lesson operations
    """
    queryset = Lesson.objects.all()
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrReadOnly]
    
    def get_serializer_class(self):
        if self.request.user.is_authenticated and self.request.user.role == 'STUDENT' and self.action == 'retrieve':  # Changed
            return LessonDetailSerializer
        return LessonSerializer
    
    def get_queryset(self):
        queryset = Lesson.objects.all()
        module_id = self.request.query_params.get('module', None)
        if module_id:
            queryset = queryset.filter(module_id=module_id)
        
        # Filter published for students
        if self.request.user.is_authenticated and self.request.user.role == 'STUDENT':  # Changed
            queryset = queryset.filter(is_published=True)
        
        return queryset.order_by('order')
    
    def perform_create(self, serializer):
        """Auto-set order if not provided"""
        module_id = self.request.data.get('module')
        module = get_object_or_404(Module, id=module_id)
        
        # Check if user is the course teacher
        if module.course.teacher != self.request.user:
            self.permission_denied(self.request)
        
        # Auto-increment order
        last_order = Lesson.objects.filter(module=module).aggregate(
            models.Max('order')
        )['order__max']
        
        order = self.request.data.get('order', (last_order or 0) + 1)
        serializer.save(module=module, order=order)
    
    @action(detail=True, methods=['post'], permission_classes=[IsStudent])
    def complete(self, request, pk=None):
        """Mark lesson as completed"""
        lesson = self.get_object()
        student = request.user
        
        # Check if student is enrolled
        if not Enrollment.objects.filter(
            student=student,
            course=lesson.module.course,
            status=Enrollment.Status.ACTIVE
        ).exists():
            return Response(
                {'error': 'Must be enrolled in course to complete lessons'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create or get completion
        completion, created = LessonCompletion.objects.get_or_create(
            student=student,
            lesson=lesson,
            defaults={
                'time_spent_seconds': request.data.get('time_spent_seconds', 0)
            }
        )
        
        if not created:
            # Update existing completion
            completion.completed_at = timezone.now()
            completion.time_spent_seconds = request.data.get(
                'time_spent_seconds', 
                completion.time_spent_seconds
            )
            completion.save()
        
        # Update enrollment progress
        enrollment = Enrollment.objects.get(
            student=student,
            course=lesson.module.course
        )
        # Record completion as explicit interaction data for engagement/difficulty analytics.
        LessonInteraction.objects.create(
            student=student,
            lesson=lesson,
            enrollment=enrollment,
            interaction_type=LessonInteraction.InteractionType.COMPLETE,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        # Backfill at least one VIEW event if none exists yet for this lesson/student.
        has_view = LessonInteraction.objects.filter(
            student=student,
            lesson=lesson,
            interaction_type=LessonInteraction.InteractionType.VIEW
        ).exists()
        if not has_view:
            LessonInteraction.objects.create(
                student=student,
                lesson=lesson,
                enrollment=enrollment,
                interaction_type=LessonInteraction.InteractionType.VIEW,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=request.META.get('REMOTE_ADDR'),
            )

        enrollment.update_progress()
        enrollment.update_last_activity()
        RiskEngine.calculate_student_risk(str(enrollment.id))
        AlertGenerator.check_and_generate_alerts(enrollment_id=str(enrollment.id))
        
        return Response({
            'message': 'Lesson marked as completed',
            'completion': LessonCompletionSerializer(completion).data,
            'progress': enrollment.progress_percentage
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsTeacher])
    def suggest_quiz(self, request, pk=None):
        """
        Generate AI-suggested quiz questions from lesson content.
        Endpoint: POST /api/lessons/{id}/suggest_quiz/
        """
        from .ai_services import AIQuizGenerator
        
        lesson = self.get_object()
        
        # Check if user is the lesson's course teacher
        if lesson.module.course.teacher != request.user:
            return Response(
                {'error': 'Only the course teacher can generate quiz suggestions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate quiz
        num_questions = request.data.get('num_questions', 5)
        result = AIQuizGenerator.suggest_quiz_from_lesson(lesson, num_questions=num_questions)
        
        if result.get('status') == 'error':
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(result, status=status.HTTP_200_OK)


class EnrollmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Enrollment operations
    """
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EnrollmentSerializer
    
    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Enrollment.objects.none()

        if user.role == 'TEACHER':
            # Teachers see enrollments for their courses
            queryset = Enrollment.objects.filter(course__teacher=user)
        elif user.role == 'STUDENT':
            # Students see their own enrollments
            queryset = Enrollment.objects.filter(student=user)
        else:
            return Enrollment.objects.none()

        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        elif user.role == 'TEACHER':
            queryset = queryset.filter(status=Enrollment.Status.ACTIVE)

        return queryset.select_related('student', 'course').order_by('-enrolled_at')
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EnrollmentDetailSerializer
        return EnrollmentSerializer
    
    @action(detail=False, methods=['get'], permission_classes=[IsStudent])
    def my_enrollments(self, request):
        """Get current student's enrollments"""
        enrollments = Enrollment.objects.filter(
            student=request.user,
            status=Enrollment.Status.ACTIVE
        )
        serializer = self.get_serializer(enrollments, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsTeacher])
    def update_risk(self, request, pk=None):
        """Manually update risk score for enrollment"""
        enrollment = self.get_object()
        risk_score = request.data.get('risk_score')
        risk_level = request.data.get('risk_level')
        
        if risk_score is not None:
            enrollment.risk_score = risk_score
        if risk_level is not None:
            enrollment.risk_level = risk_level
        
        enrollment.save()
        return Response(EnrollmentDetailSerializer(enrollment).data)


class CompetencyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Competency management
    """
    queryset = Competency.objects.all()
    serializer_class = CompetencySerializer
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrReadOnly]
    
    def get_queryset(self):
        queryset = Competency.objects.all()
        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        return queryset.order_by('category', 'name')
    
    def perform_create(self, serializer):
        """Ensure course teacher is creating competencies"""
        course_id = self.request.data.get('course')
        course = get_object_or_404(Course, id=course_id)
        
        if course.teacher != self.request.user:
            self.permission_denied(self.request)
        
        serializer.save(course=course)
    
    @action(detail=True, methods=['get'])
    def performance_heatmap(self, request, pk=None):
        """
        Get competency performance heatmap for all students in this competency.
        Endpoint: GET /api/competencies/{id}/performance_heatmap/
        """
        competency = self.get_object()
        
        # Get all student performances for this competency
        perfs = CompetencyPerformance.objects.filter(
            competency=competency
        ).select_related('student').order_by('-score_percentage')
        
        data = {
            'competency': {
                'id': str(competency.id),
                'name': competency.name,
                'category': competency.category,
            },
            'student_performances': [
                {
                    'student_id': str(perf.student.id),
                    'student_name': perf.student.display_name,
                    'score_percentage': float(perf.score_percentage),
                    'proficiency_level': perf.proficiency_level,
                    'attempts_count': perf.attempts_count,
                }
                for perf in perfs
            ]
        }
        
        return Response(data)


class LessonCompetencyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for LessonCompetency mappings
    """
    queryset = LessonCompetency.objects.all()
    serializer_class = LessonCompetencySerializer
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrReadOnly]
    
    def get_queryset(self):
        queryset = LessonCompetency.objects.all()
        lesson_id = self.request.query_params.get('lesson')
        if lesson_id:
            queryset = queryset.filter(lesson_id=lesson_id)
        return queryset.select_related('lesson', 'competency')
    
    def perform_create(self, serializer):
        """Ensure lesson's course teacher is creating mappings"""
        lesson_id = self.request.data.get('lesson')
        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        if lesson.module.course.teacher != self.request.user:
            self.permission_denied(self.request)
        
        serializer.save()


class AttendanceRecordViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Attendance tracking (Phase 4)
    """
    queryset = AttendanceRecord.objects.all()
    serializer_class = AttendanceRecordSerializer
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrReadOnly]
    
    def get_queryset(self):
        queryset = AttendanceRecord.objects.all()
        
        # Filter by course
        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        # Filter by student
        student_id = self.request.query_params.get('student')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        return queryset.select_related('student', 'course').order_by('-session_date')
    
    def perform_create(self, serializer):
        """Ensure teacher is recording for their course"""
        course_id = self.request.data.get('course')
        course = get_object_or_404(Course, id=course_id)
        
        if course.teacher != self.request.user:
            self.permission_denied(self.request)
        
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def attendance_report(self, request):
        """
        Get attendance report for a course.
        Endpoint: GET /api/attendance-records/attendance_report/?course={id}
        Returns: Attendance % per student
        """
        course_id = request.query_params.get('course')
        if not course_id:
            return Response(
                {'error': 'course parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        course = get_object_or_404(Course, id=course_id)
        
        # Check permission
        if course.teacher != request.user:
            return Response(
                {'error': 'Only course teacher can view attendance'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from django.db.models import Count, Q
        
        # Get all active students
        enrollments = Enrollment.objects.filter(
            course=course,
            status=Enrollment.Status.ACTIVE
        ).select_related('student')
        
        report = []
        for enrollment in enrollments:
            total_sessions = AttendanceRecord.objects.filter(
                course=course
            ).values('session_date').distinct().count()
            
            present_count = AttendanceRecord.objects.filter(
                student=enrollment.student,
                course=course,
                status__in=[AttendanceRecord.Status.PRESENT, AttendanceRecord.Status.LATE]
            ).count()
            
            attendance_pct = (present_count / total_sessions * 100) if total_sessions > 0 else 0
            
            report.append({
                'student_id': str(enrollment.student.id),
                'student_name': enrollment.student.display_name,
                'attendance_percentage': attendance_pct,
                'sessions_attended': present_count,
                'total_sessions': total_sessions,
                'risk_due_to_attendance': attendance_pct < 80,
            })
        
        return Response({
            'course_id': str(course.id),
            'course_title': course.title,
            'students': report
        })


class RiskPredictionViewSet(viewsets.ViewSet):
    """
    What-if simulator for risk prediction (Phase 4).
    Endpoint: POST /api/risk-prediction/predict/
    """
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    
    @action(detail=False, methods=['post'])
    def predict(self, request):
        """
        Predict risk score given hypothetical student actions.
        Input:
        {
            "enrollment_id": "...",
            "hypothetical_lessons_completed": 5,
            "hypothetical_quiz_score": 80,
            "hypothetical_days_inactive": 3
        }
        Output: Predicted risk score and risk level
        """
        enrollment_id = request.data.get('enrollment_id')
        hyp_lessons = request.data.get('hypothetical_lessons_completed', 0)
        hyp_quiz_score = request.data.get('hypothetical_quiz_score', 0)
        hyp_inactivity = request.data.get('hypothetical_days_inactive', 0)
        
        try:
            enrollment = Enrollment.objects.get(id=enrollment_id)
        except Enrollment.DoesNotExist:
            return Response({'error': 'Enrollment not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        if enrollment.course.teacher != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        # Simulate new scores
        from decimal import Decimal
        
        # Assume completing lessons improves progress by 10% per lesson
        new_progress = min(100, float(enrollment.progress_percentage) + (hyp_lessons * 10))
        
        # Weighted risk calculation: progress(40%), quiz(40%), inactivity(20%)
        progress_component = max(0, 1 - (new_progress / 100))  # Higher progress = lower risk
        quiz_component = max(0, 1 - (hyp_quiz_score / 100)) if hyp_quiz_score > 0 else float(enrollment.average_quiz_score) / 100
        inactivity_component = min(1, hyp_inactivity / 7)  # 7+ days = high inactivity risk
        
        predicted_risk_score = (
            progress_component * 0.4 +
            quiz_component * 0.4 +
            inactivity_component * 0.2
        )
        
        # Determine risk level
        if predicted_risk_score >= 0.7:
            predicted_level = 'HIGH'
        elif predicted_risk_score >= 0.4:
            predicted_level = 'MEDIUM'
        else:
            predicted_level = 'LOW'
        
        return Response({
            'enrollment_id': str(enrollment.id),
            'student_name': enrollment.student.display_name,
            'current_risk_score': float(enrollment.risk_score),
            'current_risk_level': enrollment.risk_level,
            'predicted_risk_score': float(predicted_risk_score),
            'predicted_risk_level': predicted_level,
            'improvement': float(enrollment.risk_score) - float(predicted_risk_score),
            'simulation_parameters': {
                'lessons_completed': hyp_lessons,
                'quiz_score': hyp_quiz_score,
                'days_inactive': hyp_inactivity,
            }
        })
