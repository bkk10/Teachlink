"""
Assessment views for Teachly
"""
from django.db import models  # Add this at the top with other imports
from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from .models import Quiz, Question, Answer, QuizAttempt
from .serializers import (
    QuizSerializer, QuizDetailSerializer, QuizStudentSerializer,
    QuestionSerializer, AnswerDetailSerializer,
    QuizAttemptSerializer, QuizAttemptDetailSerializer,
    QuizAttemptStartSerializer, QuizSubmitSerializer
)
from courses.models import Lesson, Enrollment
from analytics.services.risk_engine import RiskEngine
from analytics.services.alert_generator import AlertGenerator
from users.permissions import IsTeacher, IsStudent, IsTeacherOrReadOnly
import uuid


def cls_quiz_has_attempts(quiz: Quiz) -> bool:
    """Return True when any student has started/submitted an attempt for this quiz."""
    return QuizAttempt.objects.filter(
        quiz=quiz,
        status__in=[
            QuizAttempt.Status.IN_PROGRESS,
            QuizAttempt.Status.COMPLETED,
            QuizAttempt.Status.TIMED_OUT,
            QuizAttempt.Status.ABANDONED,
        ]
    ).exists()


class QuizViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Quiz operations
    """
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    queryset = Quiz.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            if self.request.user.is_authenticated and self.request.user.role == 'TEACHER':
                return QuizDetailSerializer  # ✅ Teachers see full quiz details with correct answers
            return QuizStudentSerializer     # ✅ Students see limited quiz view (no correct answers)
        return QuizSerializer
    
    def get_queryset(self):
        queryset = Quiz.objects.all()
        user = self.request.user
        
        # Filter by lesson
        lesson_id = self.request.query_params.get('lesson', None)
        if lesson_id:
            queryset = queryset.filter(lesson_id=lesson_id)

        # Filter by course
        course_id = self.request.query_params.get('course', None)
        if course_id:
            queryset = queryset.filter(lesson__module__course_id=course_id)
        
        # Teachers see all quizzes they created
        if user.is_authenticated and user.role == 'TEACHER':
            queryset = queryset.filter(lesson__module__course__teacher=user)
        # Students see only published quizzes from enrolled courses
        elif user.is_authenticated and user.role == 'STUDENT':
            queryset = queryset.filter(
                is_published=True,
                lesson__module__course__enrollments__student=user,
                lesson__module__course__enrollments__status='ACTIVE'
            ).distinct()
        
        return queryset.select_related('lesson', 'lesson__module', 'lesson__module__course').order_by('-created_at')
    
    def perform_create(self, serializer):
        """Create quiz and link to lesson"""
        lesson_id = self.request.data.get('lesson')
        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        # Check permission
        if lesson.module.course.teacher != self.request.user:
            self.permission_denied(self.request)
        
        serializer.save(lesson=lesson)
    
    @action(detail=True, methods=['post'], permission_classes=[IsStudent])
    def start(self, request, pk=None):
        """Start a quiz attempt"""
        quiz = self.get_object()

        if not quiz.is_published or quiz.total_questions <= 0 or not quiz.questions.exists():
            return Response(
                {'error': 'This quiz is not ready yet. No questions have been published.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if student is enrolled in the course
        from courses.models import Enrollment
        if not Enrollment.objects.filter(
            student=request.user,
            course=quiz.lesson.module.course,
            status='ACTIVE'
        ).exists():
            return Response(
                {'error': 'You must be enrolled in the course to take this quiz'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check attempts remaining
        attempt_count = QuizAttempt.objects.filter(
            student=request.user,
            quiz=quiz,
            status=QuizAttempt.Status.COMPLETED
        ).count()
        
        if attempt_count >= quiz.max_attempts:
            return Response(
                {'error': f'Maximum attempts ({quiz.max_attempts}) reached'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for existing in-progress attempt
        active_attempt = QuizAttempt.objects.filter(
            student=request.user,
            quiz=quiz,
            status=QuizAttempt.Status.IN_PROGRESS
        ).first()
        
        if active_attempt:
            return Response(
                {'error': 'You already have an active attempt for this quiz'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create new attempt
        attempt = QuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            attempt_number=attempt_count + 1,
            status=QuizAttempt.Status.IN_PROGRESS,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(
            QuizAttemptSerializer(attempt).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsStudent])
    def submit(self, request, pk=None):
        """Submit quiz answers"""
        quiz = self.get_object()
        attempt_id = request.data.get('attempt_id')
        responses = request.data.get('responses', {})
        
        try:
            attempt = QuizAttempt.objects.get(
                id=attempt_id,
                student=request.user,
                quiz=quiz,
                status=QuizAttempt.Status.IN_PROGRESS
            )
        except QuizAttempt.DoesNotExist:
            return Response(
                {'error': 'Active quiz attempt not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check time limit
        if quiz.time_limit_minutes > 0:
            elapsed = (timezone.now() - attempt.started_at).total_seconds() / 60
            if elapsed > quiz.time_limit_minutes:
                attempt.status = QuizAttempt.Status.TIMED_OUT
                attempt.save()
                return Response(
                    {'error': 'Time limit exceeded'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Complete the attempt
        with transaction.atomic():
            score_percentage = attempt.complete(responses)
            enrollment = Enrollment.objects.filter(
                student=request.user,
                course=quiz.lesson.module.course,
                status=Enrollment.Status.ACTIVE
            ).first()
            if enrollment:
                enrollment.update_last_activity()
                
                # AUTO-COMPLETE LESSON if student passed the quiz
                if attempt.passed:
                    from courses.models import LessonCompletion, Lesson
                    lesson = quiz.lesson
                    completion, created = LessonCompletion.objects.get_or_create(
                        student=request.user,
                        lesson=lesson,
                        defaults={
                            'completed_at': timezone.now(),
                            'time_spent_seconds': quiz.time_limit_minutes * 60 if quiz.time_limit_minutes else 1800
                        }
                    )
                    if created:
                        print(f"[AUTO-COMPLETE] Lesson '{lesson.title}' completed for {request.user.email}")
                    
                    # Recalculate enrollment progress
                    total_lessons = Lesson.objects.filter(
                        module__course=enrollment.course,
                        is_published=True
                    ).count()
                    completed_lessons = LessonCompletion.objects.filter(
                        student=request.user,
                        lesson__module__course=enrollment.course
                    ).count()
                    if total_lessons > 0:
                        enrollment.progress_percentage = (completed_lessons / total_lessons) * 100
                        enrollment.save(update_fields=['progress_percentage'])
                        print(f"[PROGRESS UPDATED] {request.user.email}: {enrollment.progress_percentage:.1f}%")
                
                # Recalculate risk and check alerts
                RiskEngine.calculate_student_risk(str(enrollment.id))
                AlertGenerator.check_and_generate_alerts(enrollment_id=str(enrollment.id))
        
        return Response({
            'attempt_id': attempt.id,
            'score': attempt.score,
            'score_percentage': score_percentage,
            'passed': attempt.passed,
            'feedback': attempt.feedback,
            'lesson_completed': attempt.passed  # Inform client that lesson was auto-completed
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsStudent])
    def my_attempts(self, request):
        """Get current student's quiz attempts"""
        attempts = QuizAttempt.objects.filter(
            student=request.user
        ).select_related('quiz', 'quiz__lesson').order_by('-started_at')[:20]
        
        serializer = QuizAttemptSerializer(attempts, many=True)
        return Response(serializer.data)


class QuestionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Question operations
    """
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    queryset = Question.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    serializer_class = QuestionSerializer
    
    def get_queryset(self):
        queryset = Question.objects.all()
        quiz_id = self.request.query_params.get('quiz', None)
        if quiz_id:
            queryset = queryset.filter(quiz_id=quiz_id)
        return queryset.order_by('order')
    
    def perform_create(self, serializer):
        """Create question and auto-set order"""
        quiz_id = self.request.data.get('quiz')
        quiz = get_object_or_404(Quiz, id=quiz_id)

        if cls_quiz_has_attempts(quiz):
            raise DRFValidationError("Quiz structure is locked because students already attempted this quiz.")
        
        # Check permission
        if quiz.lesson.module.course.teacher != self.request.user:
            self.permission_denied(self.request)
        
        # Auto-increment order
        last_order = Question.objects.filter(quiz=quiz).aggregate(
            models.Max('order')
        )['order__max']
        
        order = self.request.data.get('order', (last_order or 0) + 1)
        serializer.save(quiz=quiz, order=order)
        
        # Update quiz question count
        quiz.total_questions = quiz.questions.count()
        quiz.save(update_fields=['total_questions'])

    def perform_update(self, serializer):
        quiz = serializer.instance.quiz
        if cls_quiz_has_attempts(quiz):
            raise DRFValidationError("Quiz structure is locked because students already attempted this quiz.")
        serializer.save()

    def perform_destroy(self, instance):
        quiz = instance.quiz
        if cls_quiz_has_attempts(quiz):
            raise DRFValidationError("Quiz structure is locked because students already attempted this quiz.")
        instance.delete()


class AnswerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Answer operations
    """
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    queryset = Answer.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    serializer_class = AnswerDetailSerializer
    
    def get_queryset(self):
        queryset = Answer.objects.all()
        question_id = self.request.query_params.get('question', None)
        if question_id:
            queryset = queryset.filter(question_id=question_id)
        return queryset.order_by('order')
    
    def perform_create(self, serializer):
        """Create answer and auto-set order"""
        question_id = self.request.data.get('question')
        question = get_object_or_404(Question, id=question_id)
        quiz = question.quiz

        if cls_quiz_has_attempts(quiz):
            raise DRFValidationError("Quiz structure is locked because students already attempted this quiz.")
        
        # Check permission
        if question.quiz.lesson.module.course.teacher != self.request.user:
            self.permission_denied(self.request)
        
        # Auto-increment order
        last_order = Answer.objects.filter(question=question).aggregate(
            models.Max('order')
        )['order__max']
        
        order = self.request.data.get('order', (last_order or 0) + 1)
        serializer.save(question=question, order=order)

    def perform_update(self, serializer):
        quiz = serializer.instance.question.quiz
        if cls_quiz_has_attempts(quiz):
            raise DRFValidationError("Quiz structure is locked because students already attempted this quiz.")
        serializer.save()

    def perform_destroy(self, instance):
        quiz = instance.question.quiz
        if cls_quiz_has_attempts(quiz):
            raise DRFValidationError("Quiz structure is locked because students already attempted this quiz.")
        instance.delete()


class QuizAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing quiz attempts
    """
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    queryset = QuizAttempt.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            if self.request.user.is_authenticated and self.request.user.role == 'TEACHER':
                return QuizAttemptDetailSerializer  # 👈 INDENTED PROPERLY
            return QuizAttemptSerializer            # 👈 INDENTED PROPERLY
        return QuizAttemptSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = QuizAttempt.objects.all()
        
        if user.is_authenticated and user.role == 'TEACHER':
            # Teachers see attempts for their quizzes
            queryset = queryset.filter(
                quiz__lesson__module__course__teacher=user
            )
        else:
            # Students see only their own attempts
            queryset = queryset.filter(student=user)
        
        # Filter by quiz
        quiz_id = self.request.query_params.get('quiz', None)
        if quiz_id:
            queryset = queryset.filter(quiz_id=quiz_id)
        
        # Filter by student (teachers only)
        student_id = self.request.query_params.get('student', None)
        if student_id and user.is_authenticated and user.role == 'TEACHER':
            queryset = queryset.filter(student_id=student_id)
        
        return queryset.select_related('student', 'quiz').order_by('-started_at')
    
    @action(detail=False, methods=['get'], permission_classes=[IsTeacher])
    def quiz_performance(self, request):
        """Get performance analytics for a quiz"""
        # Add this for debugging
        print(f"🔍 QuizPerformance - User: {request.user}, Auth: {request.auth}")
        
        quiz_id = request.query_params.get('quiz_id')
        if not quiz_id:
            return Response(
                {'error': 'quiz_id parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attempts = QuizAttempt.objects.filter(
            quiz_id=quiz_id,
            status=QuizAttempt.Status.COMPLETED
        )
        
        total_attempts = attempts.count()
        if total_attempts == 0:
            return Response({
                'total_attempts': 0,
                'average_score': 0,
                'pass_rate': 0,
                'score_distribution': {}
            })
        
        # Calculate statistics
        avg_score = attempts.aggregate(
            models.Avg('score_percentage')
        )['score_percentage__avg']
        
        passed = attempts.filter(passed=True).count()
        pass_rate = (passed / total_attempts) * 100
        
        # Score distribution
        distribution = {
            '90-100': attempts.filter(score_percentage__gte=90).count(),
            '80-89': attempts.filter(score_percentage__gte=80, score_percentage__lt=90).count(),
            '70-79': attempts.filter(score_percentage__gte=70, score_percentage__lt=80).count(),
            '60-69': attempts.filter(score_percentage__gte=60, score_percentage__lt=70).count(),
            '50-59': attempts.filter(score_percentage__gte=50, score_percentage__lt=60).count(),
            '0-49': attempts.filter(score_percentage__lt=50).count(),
        }
        
        return Response({
            'total_attempts': total_attempts,
            'average_score': round(avg_score, 2) if avg_score else 0,
            'pass_rate': round(pass_rate, 2),
            'score_distribution': distribution
        })
