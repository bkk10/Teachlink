"""
Dashboard Views for TeachLink
- Teacher dashboard with risk analytics
- Student dashboard with progress tracking
- API endpoints for chart data
"""
from django.shortcuts import render, get_object_or_404
from typing import Optional, Dict, Any, List, Tuple
from django.utils import timezone
from django.db.models import Count, Q, Avg, Sum, Max, Case, When, Value, IntegerField
from rest_framework.authentication import SessionAuthentication
from django.http import JsonResponse, HttpResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import timedelta, datetime
from decimal import Decimal
import json
import os
import csv

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.shortcuts import redirect, render
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.urls import reverse
from urllib.parse import urlencode

from analytics.services.cache_services import DashboardCache, RiskCache, DifficultyCache

from courses.models import Course, Enrollment, Lesson, LessonCompletion, Module
from assessments.models import Quiz, QuizAttempt, Question, Answer
from analytics.models import Alert, RiskHistory, LessonDifficulty, LessonInteraction
from analytics.services.risk_engine import RiskEngine
from analytics.services.alert_generator import AlertGenerator
from analytics.services.difficulty_analyzer import DifficultyAnalyzer
from users.permissions import IsTeacher, IsStudent

from rest_framework.authentication import BaseAuthentication

RISK_ALERT_TYPES = [
    Alert.AlertType.DROPOUT_RISK,
    Alert.AlertType.PERFORMANCE_DROP,
    Alert.AlertType.DISENGAGEMENT,
    Alert.AlertType.MULTIPLE_FAILURES,
    Alert.AlertType.BEHIND_SCHEDULE,
]


def _notification_group_key(alert: Alert) -> Tuple[str, str]:
    """Group notifications by course and alert type for cleaner student UX."""
    return (str(alert.course_id or ''), alert.alert_type)


def _dedupe_student_notifications(alerts: List[Alert], limit: int = 10) -> Tuple[List[Alert], int]:
    """
    Keep only the newest notification per (course, alert_type) group.
    Returns deduped alerts and number of suppressed duplicates.
    """
    deduped: List[Alert] = []
    seen = set()
    suppressed_count = 0
    for alert in alerts:
        key = _notification_group_key(alert)
        if key in seen:
            suppressed_count += 1
            continue
        seen.add(key)
        deduped.append(alert)
        if len(deduped) >= limit:
            break
    return deduped, suppressed_count


def _deduped_unread_count(student) -> int:
    """Unread count aligned with deduped notification grouping."""
    unread_alerts = list(
        Alert.objects.filter(
            student=student,
            status=Alert.Status.ACTIVE
        ).order_by('-generated_at')[:200]
    )
    seen = set()
    deduped_count = 0
    for alert in unread_alerts:
        key = _notification_group_key(alert)
        if key in seen:
            continue
        seen.add(key)
        deduped_count += 1
    return deduped_count


def _collapse_student_alert_duplicates(student) -> int:
    """
    Resolve legacy duplicate alerts for a student, keeping the newest active item
    per (course, alert_type). This prevents notification spam from historical rows.
    """
    duplicate_candidates = Alert.objects.filter(
        student=student,
        status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED],
        alert_type__in=RISK_ALERT_TYPES,
    ).order_by('-generated_at')

    resolved = 0
    seen = set()
    for alert in duplicate_candidates:
        key = _notification_group_key(alert)
        if key in seen:
            alert.status = Alert.Status.RESOLVED
            alert.resolved_at = timezone.now()
            alert.intervention_outcome = "Auto-resolved duplicate notification"
            alert.save(update_fields=['status', 'resolved_at', 'intervention_outcome'])
            resolved += 1
            continue
        seen.add(key)
    return resolved


def _resolve_stale_payment_reminders(student) -> int:
    """
    Resolve stale payment reminder notifications to keep student inbox focused.
    Rules:
    - Auto-resolve reminders older than 30 days.
    - Auto-resolve reminders for courses that are already marked paid.
    """
    cutoff = timezone.now() - timedelta(days=30)
    reminders = Alert.objects.filter(
        student=student,
        status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED],
        title__icontains='payment reminder',
    ).select_related('course')

    resolved = 0
    for alert in reminders:
        should_resolve = False
        if alert.generated_at and alert.generated_at < cutoff:
            should_resolve = True
        elif alert.course_id:
            enrollment = Enrollment.objects.filter(
                student=student,
                course_id=alert.course_id,
                status=Enrollment.Status.ACTIVE,
            ).only('is_fee_paid').first()
            if enrollment and enrollment.is_fee_paid:
                should_resolve = True

        if should_resolve:
            alert.status = Alert.Status.RESOLVED
            alert.resolved_at = timezone.now()
            alert.intervention_outcome = "Auto-resolved stale payment reminder"
            alert.save(update_fields=['status', 'resolved_at', 'intervention_outcome'])
            resolved += 1

    return resolved


def difficulty_display_label(level: str) -> str:
    """Normalize stored difficulty codes to 3-band display labels."""
    mapping = {
        'LOW': 'Low Difficulty',
        'MEDIUM': 'Medium Difficulty',
        'HIGH': 'High Difficulty',
        # Legacy values
        'VERY_EASY': 'Low Difficulty',
        'EASY': 'Low Difficulty',
        'HARD': 'High Difficulty',
        'VERY_HARD': 'High Difficulty',
        'UNKNOWN': 'Unknown',
    }
    return mapping.get((level or 'UNKNOWN').upper(), 'Unknown')
# ============================================
# HTML VIEWS (Server-rendered)
# ============================================



def custom_login(request):
    """Custom login view that redirects to appropriate dashboard"""
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user)
            if user.role == 'STUDENT':
                ip_address = request.META.get('REMOTE_ADDR')
                user.update_last_activity(ip_address)
                enrollments = Enrollment.objects.filter(
                    student=user,
                    status=Enrollment.Status.ACTIVE
                )
                for enrollment in enrollments:
                    enrollment.update_last_activity()
                    # Only recalculate risk if not done in the last hour
                    last_calc = RiskHistory.objects.filter(enrollment=enrollment).order_by('-calculated_at').first()
                    if not last_calc or (timezone.now() - last_calc.calculated_at).total_seconds() > 3600:
                        RiskEngine.calculate_student_risk(str(enrollment.id))
                        AlertGenerator.check_and_generate_alerts(enrollment_id=str(enrollment.id))
            # Redirect based on role
            if user.role == 'TEACHER':
                return redirect('teacher_dashboard')
            else:
                return redirect('student_dashboard')
        else:
            messages.error(request, 'Invalid email or password')
    
    return render(request, 'dashboard/login.html')


def custom_register(request):
    """Custom registration view with role-based redirects."""
    if request.user.is_authenticated:
        if request.user.role == 'TEACHER':
            return redirect('teacher_dashboard')
        return redirect('student_dashboard')

    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        username = (request.POST.get('username') or '').strip()
        display_name = (request.POST.get('display_name') or '').strip()
        role = (request.POST.get('role') or '').strip().upper()
        password = request.POST.get('password') or ''
        password_confirm = request.POST.get('password_confirm') or ''

        User = get_user_model()
        valid_roles = {'TEACHER', 'STUDENT'}

        if not email or not username or not display_name:
            messages.error(request, 'Email, username, and display name are required.')
            return render(request, 'dashboard/register.html')
        if role not in valid_roles:
            messages.error(request, 'Please select a valid role.')
            return render(request, 'dashboard/register.html')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists.')
            return render(request, 'dashboard/register.html')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'That username is already taken.')
            return render(request, 'dashboard/register.html')
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'dashboard/register.html')

        try:
            validate_password(password)
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
            return render(request, 'dashboard/register.html')

        user = User.objects.create_user(
            email=email,
            username=username,
            display_name=display_name,
            role=role,
            password=password,
        )
        login(request, user)
        if user.role == 'TEACHER':
            return redirect('teacher_dashboard')
        return redirect('student_dashboard')

    return render(request, 'dashboard/register.html')


def custom_logout(request):
    """Session logout for dashboard web views"""
    if request.method == 'POST':
        logout(request)
        return redirect('custom_login')
    return redirect('custom_login')


def profile_view(request):
    """Unified profile page for teacher/student/admin users"""
    if not request.user.is_authenticated:
        return redirect('custom_login')

    if request.method == 'POST':
        action = request.POST.get('action', 'profile')
        if action == 'profile':
            display_name = request.POST.get('display_name', request.user.display_name).strip()
            bio = request.POST.get('bio', request.user.bio).strip()
            avatar = request.FILES.get('avatar')

            if len(display_name) < 3:
                messages.error(request, 'Display name must be at least 3 characters.')
                return redirect('dashboard_profile')
            if len(bio) > 1000:
                messages.error(request, 'Bio must be 1000 characters or less.')
                return redirect('dashboard_profile')

            if avatar:
                allowed_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
                ext = os.path.splitext(avatar.name.lower())[1]
                if ext not in allowed_exts:
                    messages.error(request, 'Avatar must be PNG, JPG, JPEG, GIF, or WEBP.')
                    return redirect('dashboard_profile')
                if avatar.size > 5 * 1024 * 1024:
                    messages.error(request, 'Avatar is too large. Maximum size is 5MB.')
                    return redirect('dashboard_profile')

            request.user.display_name = display_name or request.user.display_name
            request.user.bio = bio
            update_fields = ['display_name', 'bio']
            if avatar:
                request.user.avatar = avatar
                update_fields.append('avatar')
            request.user.save(update_fields=update_fields)
            messages.success(request, 'Profile settings updated.')
            return redirect('dashboard_profile')

        if action == 'password':
            old_password = request.POST.get('old_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not request.user.check_password(old_password):
                messages.error(request, 'Current password is incorrect.')
                return redirect('dashboard_profile')
            if new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
                return redirect('dashboard_profile')
            try:
                validate_password(new_password, user=request.user)
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages))
                return redirect('dashboard_profile')

            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Password changed successfully.')
            return redirect('dashboard_profile')

    context = {
        'member_since': request.user.date_joined,
        'last_login': request.user.last_login,
    }

    if request.user.role == 'TEACHER':
        context.update({
            'teaching_courses': Course.objects.filter(teacher=request.user).count(),
            'active_students': Enrollment.objects.filter(
                course__teacher=request.user,
                status='ACTIVE'
            ).values('student_id').distinct().count(),
            'active_alerts': Alert.objects.filter(
                teacher=request.user,
                status='ACTIVE'
            ).count(),
        })
    elif request.user.role == 'STUDENT':
        student_enrollments = Enrollment.objects.filter(
            student=request.user,
            status='ACTIVE'
        )
        context.update({
            'active_courses': student_enrollments.count(),
            'average_progress': student_enrollments.aggregate(avg=Avg('progress_percentage'))['avg'] or 0,
            'average_quiz': student_enrollments.aggregate(avg=Avg('average_quiz_score'))['avg'] or 0,
            'active_alerts': 0,
        })

    return render(request, 'dashboard/profile.html', context)


def courses_overview(request):
    """Role-aware courses and learning materials page"""
    if not request.user.is_authenticated:
        return redirect('custom_login')

    role_value = (getattr(request.user, 'role', '') or '').upper()

    if request.user.is_teacher or role_value == 'TEACHER':
        return render(request, 'dashboard/teacher/courses.html')

    if request.user.is_student or role_value == 'STUDENT':
        enrollments = list(Enrollment.objects.filter(
            student=request.user,
            status='ACTIVE'
        ).select_related('course').order_by('course__title'))
        avg_progress = (
            sum(float(item.progress_percentage or 0) for item in enrollments) / len(enrollments)
            if enrollments else
            0.0
        )

        course_rows = []
        for enrollment in enrollments:
            lessons = list(
                Lesson.objects.filter(
                    module__course=enrollment.course,
                    is_published=True
                ).select_related('module').order_by('module__order', 'order')
            )
            completed_lesson_ids = set(
                LessonCompletion.objects.filter(
                    student=request.user,
                    lesson__module__course=enrollment.course
                ).values_list('lesson_id', flat=True)
            )

            attempted_quiz_ids = QuizAttempt.objects.filter(
                student=request.user,
                quiz__lesson__module__course=enrollment.course,
                status__in=[QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT, QuizAttempt.Status.IN_PROGRESS],
            ).values_list('quiz_id', flat=True).distinct()
            quizzes = list(
                Quiz.objects.filter(
                    lesson__module__course=enrollment.course,
                ).filter(
                    Q(is_published=True, total_questions__gt=0) | Q(id__in=attempted_quiz_ids)
                ).select_related('lesson', 'lesson__module').order_by('lesson__module__order', 'lesson__order')
            )
            quizzes_by_lesson = {quiz.lesson_id: quiz for quiz in quizzes}
            attempts_summary = QuizAttempt.objects.filter(
                student=request.user,
                quiz__in=quizzes,
                status__in=[QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT],
            ).values('quiz_id').annotate(
                attempts_count=Count('id'),
                best_score=Max('score_percentage'),
                latest_submission=Max('submitted_at'),
            )
            attempts_by_quiz = {str(row['quiz_id']): row for row in attempts_summary}

            next_lesson = None
            for lesson in lessons:
                if lesson.id not in completed_lesson_ids:
                    next_lesson = lesson
                    break

            lesson_rows = []
            for lesson in lessons[:10]:
                quiz = quizzes_by_lesson.get(lesson.id)
                attempt_info = attempts_by_quiz.get(str(quiz.id)) if quiz else None
                attempts_used = int(attempt_info['attempts_count']) if attempt_info else 0
                attempts_left = max(int(quiz.max_attempts or 0) - attempts_used, 0) if quiz else 0
                quiz_available = bool(quiz and quiz.is_published and int(quiz.total_questions or 0) > 0)
                lesson_rows.append({
                    'lesson': lesson,
                    'completed': lesson.id in completed_lesson_ids,
                    'open_url': reverse('open_lesson_material', kwargs={'lesson_id': lesson.id}),
                    'quiz': quiz,
                    'quiz_available': quiz_available,
                    'quiz_attempts_url': reverse('student_quiz_attempts', kwargs={'quiz_id': quiz.id}) if quiz else '',
                    'quiz_attempts_used': attempts_used,
                    'quiz_attempts_left': attempts_left,
                    'quiz_can_take': bool(quiz_available and attempts_left > 0),
                    'quiz_best_score': float(attempt_info['best_score'] or 0) if attempt_info else None,
                })

            quiz_rows = []
            for quiz in quizzes[:8]:
                attempt_info = attempts_by_quiz.get(str(quiz.id))
                attempts_used = int(attempt_info['attempts_count']) if attempt_info else 0
                attempts_left = max(int(quiz.max_attempts or 0) - attempts_used, 0)
                quiz_available = bool(quiz.is_published and int(quiz.total_questions or 0) > 0)
                quiz_rows.append({
                    'quiz': quiz,
                    'attempts_used': attempts_used,
                    'attempts_left': attempts_left,
                    'best_score': float(attempt_info['best_score'] or 0) if attempt_info else 0.0,
                    'latest_submission': attempt_info['latest_submission'] if attempt_info else None,
                    'quiz_available': quiz_available,
                    'can_take': bool(quiz_available and attempts_left > 0),
                    'attempts_url': reverse('student_quiz_attempts', kwargs={'quiz_id': quiz.id}),
                })

            completion_rate = round((len(completed_lesson_ids) / len(lessons)) * 100, 1) if lessons else 0.0
            course_rows.append({
                'enrollment': enrollment,
                'lessons': lesson_rows,
                'quiz_rows': quiz_rows,
                'total_lessons': len(lessons),
                'completed_lessons': len(completed_lesson_ids),
                'completion_rate': completion_rate,
                'next_lesson': next_lesson,
                'course_workspace_url': reverse('student_course_quizzes', kwargs={'course_id': enrollment.course.id}),
                'anchor_id': f"course-{enrollment.course.id}",
            })

        return render(
            request,
            'dashboard/student/courses.html',
            {
                'course_rows': course_rows,
                'total_courses': len(enrollments),
                'avg_progress': round(float(avg_progress), 1),
            }
        )

    if request.user.is_staff or request.user.is_superuser:
        courses = Course.objects.select_related('teacher').order_by('-created_at')
        return render(request, 'dashboard/admin/courses.html', {'courses': courses})

    context = {}

    if request.user.role == 'TEACHER':
        if request.method == 'POST':
            action = request.POST.get('action', '')
            course_id = request.POST.get('course_id', '')

            course = Course.objects.filter(id=course_id, teacher=request.user).first()
            if not course:
                messages.error(request, 'Invalid course selected.')
                return redirect('dashboard_courses')

            if action == 'add_lesson':
                module_id = request.POST.get('module_id', '').strip()
                module_title = request.POST.get('module_title', '').strip()
                lesson_title = request.POST.get('lesson_title', '').strip()
                content_type = request.POST.get('content_type', 'TEXT').strip() or 'TEXT'
                content_text = request.POST.get('content_text', '').strip()
                external_url = request.POST.get('external_url', '').strip()
                estimated_minutes = int(request.POST.get('estimated_minutes', '10') or '10')
                resource_file = request.FILES.get('resource_file')

                if resource_file:
                    allowed_exts = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.txt'}
                    ext = os.path.splitext(resource_file.name.lower())[1]
                    max_size = 10 * 1024 * 1024  # 10MB
                    if ext not in allowed_exts:
                        messages.error(request, 'Unsupported file type. Allowed: PDF, DOC, DOCX, PPT, PPTX, TXT.')
                        return redirect('dashboard_courses')
                    if resource_file.size > max_size:
                        messages.error(request, 'File too large. Maximum allowed size is 10MB.')
                        return redirect('dashboard_courses')

                if not lesson_title:
                    messages.error(request, 'Lesson title is required.')
                    return redirect('dashboard_courses')

                module = None
                if module_id:
                    module = Module.objects.filter(id=module_id, course=course).first()
                if not module:
                    if not module_title:
                        module_title = 'General Module'
                    next_module_order = (Module.objects.filter(course=course).aggregate(max_order=Max('order'))['max_order'] or 0) + 1
                    module = Module.objects.create(
                        course=course,
                        title=module_title,
                        description=f'Auto-created module for {course.title}',
                        order=next_module_order,
                        estimated_minutes=0,
                    )

                next_lesson_order = (Lesson.objects.filter(module=module).aggregate(max_order=Max('order'))['max_order'] or 0) + 1
                Lesson.objects.create(
                    module=module,
                    title=lesson_title,
                    content_type=content_type,
                    content_text=content_text,
                    external_url=external_url,
                    resource_file=resource_file,
                    order=next_lesson_order,
                    estimated_minutes=max(1, estimated_minutes),
                    is_published=True,
                )

                DifficultyAnalyzer.analyze_course_difficulties(str(course.id))
                AlertGenerator.check_and_generate_alerts(course_id=str(course.id))
                messages.success(request, f'Lesson "{lesson_title}" created and analytics refreshed.')
                return redirect('dashboard_courses')

            if action == 'add_quiz':
                lesson_id = request.POST.get('lesson_id', '').strip()
                quiz_title = request.POST.get('quiz_title', '').strip()
                quiz_description = request.POST.get('quiz_description', '').strip()
                question_text = request.POST.get('question_text', '').strip()
                passing_score = int(request.POST.get('passing_score', '70') or '70')
                correct_answer = request.POST.get('correct_answer', '1')

                lesson = Lesson.objects.filter(id=lesson_id, module__course=course).first()
                if not lesson:
                    messages.error(request, 'Invalid lesson selected for quiz.')
                    return redirect('dashboard_courses')
                if not question_text:
                    messages.error(request, 'Question text is required.')
                    return redirect('dashboard_courses')

                quiz, created = Quiz.objects.get_or_create(
                    lesson=lesson,
                    defaults={
                        'title': quiz_title or f'{lesson.title} Quiz',
                        'description': quiz_description,
                        'quiz_type': 'MCQ',
                        'passing_score': max(0, min(100, passing_score)),
                        'is_published': True,
                    }
                )

                if not created:
                    quiz.title = quiz_title or quiz.title
                    quiz.description = quiz_description
                    quiz.passing_score = max(0, min(100, passing_score))
                    quiz.is_published = True
                    quiz.save()

                question_order = (Question.objects.filter(quiz=quiz).aggregate(max_order=Max('order'))['max_order'] or 0) + 1
                question = Question.objects.create(
                    quiz=quiz,
                    question_type='MCQ',
                    text=question_text,
                    points=1,
                    order=question_order,
                )

                answers = [
                    request.POST.get('answer_1', '').strip(),
                    request.POST.get('answer_2', '').strip(),
                    request.POST.get('answer_3', '').strip(),
                    request.POST.get('answer_4', '').strip(),
                ]
                valid_answers = [a for a in answers if a]
                if len(valid_answers) < 2:
                    question.delete()
                    messages.error(request, 'Provide at least 2 answer options.')
                    return redirect('dashboard_courses')

                try:
                    correct_index = max(1, min(4, int(correct_answer))) - 1
                except ValueError:
                    correct_index = 0

                answer_order = 1
                for idx, answer_text in enumerate(answers):
                    if not answer_text:
                        continue
                    Answer.objects.create(
                        question=question,
                        text=answer_text,
                        is_correct=(idx == correct_index),
                        order=answer_order,
                    )
                    answer_order += 1

                quiz.total_questions = quiz.questions.count()
                quiz.save(update_fields=['total_questions'])

                DifficultyAnalyzer.analyze_lesson_difficulty(str(lesson.id))
                AlertGenerator.check_and_generate_alerts(course_id=str(course.id))
                messages.success(request, f'Quiz "{quiz.title}" saved with a new question and answers.')
                return redirect('dashboard_courses')

            messages.error(request, 'Unknown action.')
            return redirect('dashboard_courses')

        courses = Course.objects.filter(
            teacher=request.user
        ).select_related('teacher').order_by('title')

        teacher_courses = []
        for course in courses:
            lessons = Lesson.objects.filter(
                module__course=course
            ).select_related('module').order_by('module__order', 'order')

            quizzes_count = Quiz.objects.filter(lesson__module__course=course).count()
            resources_count = lessons.filter(
                Q(resource_file__isnull=False) | ~Q(external_url='')
            ).count()
            students_count = Enrollment.objects.filter(course=course, status='ACTIVE').count()

            lesson_metrics = []
            for lesson in lessons[:12]:
                views_qs = LessonInteraction.objects.filter(
                    lesson=lesson,
                    interaction_type=LessonInteraction.InteractionType.VIEW
                )
                view_count = views_qs.count()
                unique_users = views_qs.values('student_id').distinct().count()
                attempts_qs = QuizAttempt.objects.filter(
                    quiz__lesson=lesson,
                    status='COMPLETED'
                )
                attempts = attempts_qs.count()
                pass_rate = 0
                if attempts > 0:
                    pass_rate = round((attempts_qs.filter(passed=True).count() / attempts) * 100, 1)

                difficulty = getattr(lesson, 'difficulty_analysis', None)
                lesson_metrics.append({
                    'lesson': lesson,
                    'views': view_count,
                    'unique_users': unique_users,
                    'attempts': attempts,
                    'pass_rate': pass_rate,
                    'difficulty_level': difficulty.difficulty_level if difficulty else 'UNKNOWN',
                    'difficulty_label': difficulty_display_label(difficulty.difficulty_level if difficulty else 'UNKNOWN'),
                    'difficulty_score': float(difficulty.difficulty_score) if difficulty else 0.0,
                })

            teacher_courses.append({
                'course': course,
                'students_count': students_count,
                'modules_count': course.modules.count(),
                'lessons_count': lessons.count(),
                'quizzes_count': quizzes_count,
                'resources_count': resources_count,
                'preview_lessons': lessons[:8],
                'modules': Module.objects.filter(course=course).order_by('order'),
                'lesson_options': lessons[:30],
                'lesson_metrics': lesson_metrics,
                'hard_lessons': DifficultyAnalyzer.get_hardest_lessons(str(course.id), limit=5),
            })

        context['teacher_courses'] = teacher_courses

    elif request.user.role == 'STUDENT':
        enrollments = Enrollment.objects.filter(
            student=request.user,
            status='ACTIVE'
        ).select_related('course', 'course__teacher').order_by('course__title')

        student_courses = []
        for enrollment in enrollments:
            lessons = Lesson.objects.filter(
                module__course=enrollment.course,
                is_published=True
            ).select_related('module').order_by('module__order', 'order')

            lesson_rows = []
            for lesson in lessons[:15]:
                has_quiz = Quiz.objects.filter(lesson=lesson).exists()
                lesson_rows.append({
                    'lesson': lesson,
                    'has_quiz': has_quiz,
                })

            student_courses.append({
                'enrollment': enrollment,
                'lessons': lesson_rows,
                'total_lessons': lessons.count(),
            })

        context['student_courses'] = student_courses
    else:
        return render(request, 'dashboard/unauthorized.html')

    return render(request, 'dashboard/courses.html', context)


def open_lesson_material(request, lesson_id):
    """Track lesson material usage and redirect to the material link/file."""
    if not request.user.is_authenticated:
        return redirect('custom_login')

    lesson = get_object_or_404(Lesson.objects.select_related('module', 'module__course'), id=lesson_id)

    if request.user.role == 'STUDENT':
        enrollment = Enrollment.objects.filter(
            student=request.user,
            course=lesson.module.course,
            status='ACTIVE'
        ).first()
        if not enrollment:
            return render(request, 'dashboard/unauthorized.html')

        LessonInteraction.objects.create(
            student=request.user,
            lesson=lesson,
            enrollment=enrollment,
            interaction_type=LessonInteraction.InteractionType.VIEW,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        enrollment.update_last_activity()
        RiskEngine.calculate_student_risk(str(enrollment.id))
        DifficultyAnalyzer.analyze_lesson_difficulty(str(lesson.id))
        AlertGenerator.check_and_generate_alerts(enrollment_id=str(enrollment.id))
        completed = LessonCompletion.objects.filter(
            student=request.user,
            lesson=lesson
        ).exists()
        quiz = Quiz.objects.filter(
            lesson=lesson
        ).first()
        return render(request, 'dashboard/student/lesson_view.html', {
            'lesson': lesson,
            'course': lesson.module.course,
            'completed': completed,
            'quiz': quiz,
            'quiz_available': bool(quiz and quiz.is_published and int(quiz.total_questions or 0) > 0),
            'course_back_url': reverse('student_course_quizzes', kwargs={'course_id': lesson.module.course.id}),
        })

    if lesson.external_url:
        return redirect(lesson.external_url)
    if lesson.resource_file:
        return redirect(lesson.resource_file.url)
    if lesson.video_url:
        return redirect(lesson.video_url)

    return redirect('dashboard_courses')

# Remove this import
# from django.contrib.auth.decorators import login_required

def teacher_dashboard(request):
    """Main teacher dashboard view"""
    # Check if user is authenticated
    if not request.user.is_authenticated:
        return redirect('custom_login')
    
    # Check role
    if request.user.role != 'TEACHER':
        return render(request, 'dashboard/unauthorized.html')
    
    context = {
        'teacher_name': request.user.display_name,
        'current_date': timezone.now().date(),
    }
    return render(request, 'dashboard/teacher/dashboard.html', context)


def teacher_course_analytics(request, course_id):
    """Course-specific analytics page for teachers."""
    if not request.user.is_authenticated:
        return redirect('custom_login')
    if request.user.role != 'TEACHER':
        return render(request, 'dashboard/unauthorized.html')

    course = get_object_or_404(
        Course.objects.select_related('teacher'),
        id=course_id,
        teacher=request.user,
    )

    enrollments = Enrollment.objects.filter(
        course=course,
        status=Enrollment.Status.ACTIVE
    ).select_related('student').order_by('-risk_score', 'student__display_name')

    risk_summary = {
        'total': enrollments.count(),
        'high': enrollments.filter(risk_level__in=['HIGH', 'CRITICAL']).count(),
        'medium': enrollments.filter(risk_level='MEDIUM').count(),
        'low': enrollments.filter(risk_level='LOW').count(),
    }

    lessons = Lesson.objects.filter(
        module__course=course
    ).select_related('module').order_by('module__order', 'order')

    lesson_rows = []
    for lesson in lessons:
        analyzed = DifficultyAnalyzer.analyze_lesson_difficulty(str(lesson.id))
        has_quiz = hasattr(lesson, 'quiz')
        attempts_qs = QuizAttempt.objects.filter(
            quiz__lesson=lesson,
            status=QuizAttempt.Status.COMPLETED
        )
        attempts = attempts_qs.count() if has_quiz else None
        if has_quiz:
            failures = attempts_qs.filter(
                score_percentage__lt=lesson.quiz.passing_score
            ).count()
            failure_rate = round((failures / attempts) * 100, 1) if attempts > 0 else 0.0
        else:
            failures = None
            failure_rate = None
        accesses = int((analyzed or {}).get('statistics', {}).get('total_views', 0))

        # Per-student access/attempt/failure breakdown for drill-down UI.
        access_qs = list(LessonInteraction.objects.filter(
            lesson=lesson,
            interaction_type=LessonInteraction.InteractionType.VIEW
        ).values('student_id', 'student__display_name').annotate(
            access_count=Count('id')
        ).order_by('-access_count', 'student__display_name'))

        access_counts_by_student = {}
        student_name_by_id = {}
        for row in access_qs:
            student_id = row['student_id']
            access_counts_by_student[student_id] = int(row['access_count'] or 0)
            student_name_by_id[student_id] = row['student__display_name']

        # Ensure completed lessons count as at least one access.
        completion_qs = LessonCompletion.objects.filter(
            lesson=lesson
        ).values('student_id', 'student__display_name').annotate(
            completion_count=Count('id')
        )
        for row in completion_qs:
            student_id = row['student_id']
            student_name_by_id[student_id] = row['student__display_name']
            access_counts_by_student[student_id] = max(access_counts_by_student.get(student_id, 0), 1)

        access_students_count = len(access_counts_by_student)

        student_breakdown_map = {
            student_id: {
                'student_name': student_name_by_id.get(student_id, 'Unknown Student'),
                'accesses': access_count,
                'attempts': None if not has_quiz else 0,
                'failures': None if not has_quiz else 0,
            }
            for student_id, access_count in access_counts_by_student.items()
        }

        if has_quiz:
            attempts_by_student = QuizAttempt.objects.filter(
                quiz=lesson.quiz,
                status=QuizAttempt.Status.COMPLETED
            ).values('student_id', 'student__display_name').annotate(
                attempts=Count('id'),
                failures=Count('id', filter=Q(score_percentage__lt=lesson.quiz.passing_score))
            ).order_by('-attempts', 'student__display_name')

            for row in attempts_by_student:
                student_id = row['student_id']
                if student_id not in student_breakdown_map:
                    student_breakdown_map[student_id] = {
                        'student_name': row['student__display_name'],
                        'accesses': 0,
                        'attempts': 0,
                        'failures': 0,
                    }
                student_breakdown_map[student_id]['attempts'] = row['attempts']
                student_breakdown_map[student_id]['failures'] = row['failures']

        student_access_breakdown = sorted(
            student_breakdown_map.values(),
            key=lambda item: (
                -int(item['accesses'] or 0),
                -int(item['attempts'] if item['attempts'] is not None else -1),
                item['student_name']
            )
        )

        difficulty_level = (analyzed or {}).get('difficulty_level', 'UNKNOWN')

        lesson_rows.append({
            'lesson_id': str(lesson.id),
            'lesson_title': lesson.title,
            'has_quiz': has_quiz,
            'quiz_id': str(lesson.quiz.id) if has_quiz else '',
            'attempts': attempts,
            'failures': failures,
            'failure_rate': failure_rate,
            'accesses': accesses,
            'access_students_count': access_students_count,
            'difficulty_level': difficulty_level,
            'difficulty_label': difficulty_display_label(difficulty_level),
            'student_access_breakdown': student_access_breakdown,
        })

    context = {
        'teacher_name': request.user.display_name,
        'course': course,
        'risk_summary': risk_summary,
        'enrollments': enrollments[:50],
        'lesson_rows': lesson_rows,
    }
    return render(request, 'dashboard/teacher/course_analytics.html', context)


def teacher_quiz_builder(request, quiz_id):
    """Teacher page to configure quiz/CAT settings and questions."""
    if not request.user.is_authenticated:
        return redirect('custom_login')
    if request.user.role != 'TEACHER':
        return render(request, 'dashboard/unauthorized.html')

    quiz = get_object_or_404(
        Quiz.objects.select_related('lesson', 'lesson__module', 'lesson__module__course'),
        id=quiz_id,
        lesson__module__course__teacher=request.user,
    )
    course = quiz.lesson.module.course

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        quiz_locked = QuizAttempt.objects.filter(
            quiz=quiz,
            status__in=[
                QuizAttempt.Status.IN_PROGRESS,
                QuizAttempt.Status.COMPLETED,
                QuizAttempt.Status.TIMED_OUT,
                QuizAttempt.Status.ABANDONED,
            ]
        ).exists()

        if action == 'save_quiz_meta':
            title = (request.POST.get('title') or '').strip()
            description = (request.POST.get('description') or '').strip()
            passing_score = request.POST.get('passing_score')
            time_limit = request.POST.get('time_limit_minutes')
            max_attempts = request.POST.get('max_attempts')

            if not title:
                messages.error(request, 'Quiz title is required.')
                return redirect('teacher_quiz_builder', quiz_id=quiz.id)

            try:
                passing_score_value = max(0, min(100, int(passing_score or quiz.passing_score or 70)))
                time_limit_value = max(0, int(time_limit or quiz.time_limit_minutes or 0))
                max_attempts_value = max(1, int(max_attempts or quiz.max_attempts or 1))
            except ValueError:
                messages.error(request, 'Settings contain invalid numeric values.')
                return redirect('teacher_quiz_builder', quiz_id=quiz.id)

            quiz.title = title
            quiz.description = description
            quiz.passing_score = passing_score_value
            quiz.time_limit_minutes = time_limit_value
            quiz.max_attempts = max_attempts_value
            quiz.total_questions = quiz.questions.count()
            quiz.is_published = quiz.total_questions > 0
            quiz.save()
            if quiz.is_published:
                messages.success(request, 'Assessment settings updated.')
            else:
                messages.warning(request, 'Assessment saved as draft. Add at least one question to publish.')
            return redirect('teacher_quiz_builder', quiz_id=quiz.id)

        if action == 'add_question':
            if quiz_locked:
                messages.error(request, 'Cannot add questions. Students have already started this assessment.')
                return redirect('teacher_quiz_builder', quiz_id=quiz.id)

            question_text = (request.POST.get('question_text') or '').strip()
            options = [
                (request.POST.get('option_1') or '').strip(),
                (request.POST.get('option_2') or '').strip(),
                (request.POST.get('option_3') or '').strip(),
                (request.POST.get('option_4') or '').strip(),
            ]
            options = [opt for opt in options if opt]
            try:
                correct_index = int(request.POST.get('correct_index') or 1)
            except ValueError:
                correct_index = 1

            if not question_text:
                messages.error(request, 'Question text is required.')
                return redirect('teacher_quiz_builder', quiz_id=quiz.id)
            if len(options) < 2:
                messages.error(request, 'Add at least two answer options.')
                return redirect('teacher_quiz_builder', quiz_id=quiz.id)
            if correct_index < 1 or correct_index > len(options):
                messages.error(request, 'Correct answer position must match one of the filled options.')
                return redirect('teacher_quiz_builder', quiz_id=quiz.id)

            next_order = (quiz.questions.aggregate(max_order=Max('order'))['max_order'] or 0) + 1
            question = Question.objects.create(
                quiz=quiz,
                question_type=Question.QuestionType.MULTIPLE_CHOICE,
                text=question_text,
                points=1,
                order=next_order,
            )
            for idx, option in enumerate(options, start=1):
                Answer.objects.create(
                    question=question,
                    text=option,
                    is_correct=(idx == correct_index),
                    order=idx,
                )
            quiz.total_questions = quiz.questions.count()
            quiz.is_published = quiz.total_questions > 0
            quiz.save(update_fields=['total_questions', 'is_published'])
            messages.success(request, 'Question added successfully.')
            return redirect('teacher_quiz_builder', quiz_id=quiz.id)

        if action == 'delete_question':
            if quiz_locked:
                messages.error(request, 'Cannot remove questions. Students have already started this assessment.')
                return redirect('teacher_quiz_builder', quiz_id=quiz.id)

            question_id = (request.POST.get('question_id') or '').strip()
            question = Question.objects.filter(id=question_id, quiz=quiz).first()
            if not question:
                messages.error(request, 'Question not found.')
                return redirect('teacher_quiz_builder', quiz_id=quiz.id)
            question.delete()
            quiz.total_questions = quiz.questions.count()
            quiz.is_published = quiz.total_questions > 0
            quiz.save(update_fields=['total_questions', 'is_published'])
            messages.success(request, 'Question removed.')
            return redirect('teacher_quiz_builder', quiz_id=quiz.id)

    questions = list(quiz.questions.prefetch_related('answers').order_by('order'))
    question_rows = []
    for question in questions:
        answers = list(question.answers.all().order_by('order'))
        question_rows.append({
            'question': question,
            'answers': answers,
        })

    context = {
        'course': course,
        'quiz': quiz,
        'question_rows': question_rows,
    }
    return render(request, 'dashboard/teacher/quiz_builder.html', context)


def student_dashboard(request):
    """Main student dashboard view"""
    # Check if user is authenticated
    if not request.user.is_authenticated:
        return redirect('custom_login')
    
    # Check role
    if request.user.role != 'STUDENT':
        return render(request, 'dashboard/unauthorized.html')
    
    lessons = Lesson.objects.filter(
        module__course__enrollments__student=request.user,
        module__course__enrollments__status='ACTIVE',
        is_published=True
    ).select_related('module', 'module__course').distinct().order_by('module__course__title', 'module__order', 'order')[:12]

    learning_materials = []
    for lesson in lessons:
        learning_materials.append({
            'lesson_id': lesson.id,
            'course_title': lesson.module.course.title,
            'module_title': lesson.module.title,
            'lesson_title': lesson.title,
            'content_type': lesson.get_content_type_display(),
            'resource_file': lesson.resource_file.url if lesson.resource_file else '',
            'external_url': lesson.external_url,
            'has_quiz': Quiz.objects.filter(lesson=lesson).exists(),
        })

    enrollments = Enrollment.objects.filter(
        student=request.user,
        status='ACTIVE'
    ).select_related('course')

    # Student risk summary card
    total_enrollments = enrollments.count()
    if total_enrollments > 0:
        overall_risk_level = enrollments.order_by(
            Case(
                When(risk_level='CRITICAL', then=Value(4)),
                When(risk_level='HIGH', then=Value(3)),
                When(risk_level='MEDIUM', then=Value(2)),
                When(risk_level='LOW', then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).first().risk_level
        overall_risk_score = float(enrollments.aggregate(Avg('risk_score'))['risk_score__avg'] or 0)
        last_activity = enrollments.order_by('-last_activity').first().last_activity
        missed_assessments = 0
        for e in enrollments:
            total_quizzes = Quiz.objects.filter(lesson__module__course=e.course, is_published=True, total_questions__gt=0).count()
            completed_quizzes = QuizAttempt.objects.filter(student=request.user, quiz__lesson__module__course=e.course, status__in=[QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT]).values('quiz_id').distinct().count()
            missed_assessments += max(0, total_quizzes - completed_quizzes)
    else:
        overall_risk_level = 'UNKNOWN'
        overall_risk_score = 0.0
        last_activity = None
        missed_assessments = 0

    active_alerts = Alert.objects.filter(
        student=request.user,
        status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED]
    ).count()

    context = {
        'student_name': request.user.display_name,
        'current_date': timezone.now().date(),
        'learning_materials': learning_materials,
        'enrollments': enrollments,
        'risk_summary': {
            'risk_level': overall_risk_level,
            'risk_score_pct': round(overall_risk_score * 100.0, 1),
            'missed_assessments': missed_assessments,
            'last_activity': last_activity,
            'active_alerts': active_alerts,
        }
    }
    return render(request, 'dashboard/student/dashboard.html', context)


def _format_attempt_duration(seconds_value) -> str:
    """Format duration seconds into human-readable string."""
    try:
        total_seconds = int(seconds_value or 0)
    except (TypeError, ValueError):
        total_seconds = 0
    minutes, seconds = divmod(max(total_seconds, 0), 60)
    if minutes <= 0:
        return f"{seconds} secs"
    if seconds == 0:
        return f"{minutes} mins"
    return f"{minutes} mins {seconds} secs"


def student_course_quizzes(request, course_id):
    """Student list of quizzes/CATs for a specific enrolled course."""
    if not request.user.is_authenticated:
        return redirect('custom_login')
    if request.user.role != 'STUDENT':
        return render(request, 'dashboard/unauthorized.html')

    enrollment = get_object_or_404(
        Enrollment.objects.select_related('course', 'course__teacher'),
        student=request.user,
        course_id=course_id,
        status=Enrollment.Status.ACTIVE,
    )
    course = enrollment.course

    # Get lessons with completion status
    lessons = Lesson.objects.filter(
        module__course=course,
        is_published=True
    ).select_related('module').order_by('module__order', 'order')

    lesson_completions = LessonCompletion.objects.filter(
        student=request.user,
        lesson__module__course=course
    ).values_list('lesson_id', flat=True)

    quizzes_by_lesson = {
        quiz.lesson_id: quiz
        for quiz in Quiz.objects.filter(lesson__in=lessons).select_related('lesson')
    }

    lesson_rows = []
    for lesson in lessons:
        completed = lesson.id in lesson_completions
        quiz = quizzes_by_lesson.get(lesson.id)
        lesson_rows.append({
            'lesson': lesson,
            'completed': completed,
            'quiz_id': str(quiz.id) if quiz else '',
            'quiz_available': bool(quiz and quiz.is_published and int(quiz.total_questions or 0) > 0),
        })

    attempted_quiz_ids = QuizAttempt.objects.filter(
        student=request.user,
        quiz__lesson__module__course=course,
        status__in=[QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT, QuizAttempt.Status.IN_PROGRESS],
    ).values_list('quiz_id', flat=True).distinct()

    quizzes = list(
        Quiz.objects.filter(
            lesson__module__course=course,
        )
        .filter(
            Q(is_published=True, total_questions__gt=0) | Q(id__in=attempted_quiz_ids)
        )
        .select_related('lesson', 'lesson__module')
        .order_by('lesson__module__order', 'lesson__order')
    )

    attempts_by_quiz = {}
    attempts = QuizAttempt.objects.filter(
        student=request.user,
        quiz__lesson__module__course=course,
        status__in=[QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT],
    ).select_related('quiz').order_by('attempt_number')

    for attempt in attempts:
        key = str(attempt.quiz_id)
        attempts_by_quiz.setdefault(key, []).append(attempt)

    quiz_rows = []
    for quiz in quizzes:
        quiz_attempts = attempts_by_quiz.get(str(quiz.id), [])
        best_attempt = max(quiz_attempts, key=lambda item: float(item.score_percentage or 0)) if quiz_attempts else None
        latest_attempt = quiz_attempts[-1] if quiz_attempts else None
        attempts_used = len(quiz_attempts)
        attempts_left = max(int(quiz.max_attempts or 0) - attempts_used, 0)
        final_score = float(best_attempt.score_percentage or 0) if best_attempt else 0
        quiz_available = bool(quiz.is_published and int(quiz.total_questions or 0) > 0)
        if attempts_used > 0 and not quiz_available:
            status_label = 'History Only'
        elif attempts_used > 0:
            status_label = 'Completed'
        else:
            status_label = 'Not Attempted'
        quiz_rows.append({
            'quiz': quiz,
            'attempts_used': attempts_used,
            'attempts_left': attempts_left,
            'best_attempt': best_attempt,
            'latest_attempt': latest_attempt,
            'final_score': round(final_score, 2),
            'quiz_available': quiz_available,
            'can_take': bool(quiz_available and attempts_left > 0),
            'status_label': status_label,
        })

    context = {
        'course': course,
        'enrollment': enrollment,
        'lesson_rows': lesson_rows,
        'quiz_rows': quiz_rows,
        'draft_quiz_count': Quiz.objects.filter(
            lesson__module__course=course,
            is_published=False,
            total_questions__gt=0
        ).count(),
    }
    return render(request, 'dashboard/student/course_quizzes.html', context)


def student_quiz_attempts(request, quiz_id):
    """Student attempt summary page for a specific quiz/CAT."""
    if not request.user.is_authenticated:
        return redirect('custom_login')
    if request.user.role != 'STUDENT':
        return render(request, 'dashboard/unauthorized.html')

    quiz = get_object_or_404(
        Quiz.objects.select_related('lesson', 'lesson__module', 'lesson__module__course'),
        id=quiz_id,
    )
    course = quiz.lesson.module.course
    enrollment = Enrollment.objects.filter(
        student=request.user,
        course=course,
        status=Enrollment.Status.ACTIVE,
    ).first()
    if not enrollment:
        return render(request, 'dashboard/unauthorized.html')

    # Prevent opening placeholder quizzes with no actual questions.
    if quiz.total_questions <= 0 or not quiz.questions.exists():
        messages.warning(request, 'This assessment is still being prepared and has no questions yet.')
        return redirect('student_course_quizzes', course_id=course.id)

    attempt_qs = QuizAttempt.objects.filter(
        student=request.user,
        quiz=quiz,
        status__in=[QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT, QuizAttempt.Status.IN_PROGRESS],
    ).order_by('attempt_number')
    attempts_all = list(attempt_qs)
    attempts = [a for a in attempts_all if a.status in [QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT]]
    active_attempt = next((a for a in attempts_all if a.status == QuizAttempt.Status.IN_PROGRESS), None)

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
        if action == 'submit_quiz':
            if quiz.total_questions <= 0 or not quiz.is_published or not quiz.questions.exists():
                messages.warning(request, 'This assessment is not currently available.')
                return redirect('student_quiz_attempts', quiz_id=quiz.id)

            attempts_used_now = len([a for a in attempts_all if a.status in [QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT]])
            if attempts_used_now >= int(quiz.max_attempts or 0) and not active_attempt:
                messages.warning(request, 'No attempts remaining for this assessment.')
                return redirect('student_quiz_attempts', quiz_id=quiz.id)

            responses = {}
            quiz_questions = list(quiz.questions.order_by('order'))
            for question in quiz_questions:
                selected = (request.POST.get(f"q_{question.id}") or '').strip()
                if selected:
                    responses[str(question.id)] = selected

            attempt = active_attempt
            if not attempt:
                next_attempt_number = (max([a.attempt_number for a in attempts_all], default=0) + 1)
                attempt = QuizAttempt.objects.create(
                    student=request.user,
                    quiz=quiz,
                    attempt_number=next_attempt_number,
                    status=QuizAttempt.Status.IN_PROGRESS,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )

            try:
                attempt.complete(responses)
                enrollment.update_last_activity()
                RiskEngine.calculate_student_risk(str(enrollment.id))
                AlertGenerator.check_and_generate_alerts(enrollment_id=str(enrollment.id))
                messages.success(
                    request,
                    f'Quiz submitted. You scored {float(attempt.score_percentage or 0):.2f}%.'
                )
            except ValueError as exc:
                messages.error(request, str(exc))
            return redirect('student_quiz_attempts', quiz_id=quiz.id)

    best_attempt = max(attempts, key=lambda item: float(item.score_percentage or 0)) if attempts else None
    attempts_allowed = int(quiz.max_attempts or 0)
    attempts_used = len(attempts)
    attempts_left = max(attempts_allowed - attempts_used, 0)
    final_grade = (
        f"{float(best_attempt.score or 0):.2f}/{float(best_attempt.max_possible_score or 0):.2f}"
        if best_attempt else
        f"0.00/{float(quiz.total_questions or 0):.2f}"
    )
    final_percentage = float(best_attempt.score_percentage or 0) if best_attempt else 0.0

    attempt_rows = []
    for attempt in attempts:
        submitted_label = attempt.submitted_at
        if submitted_label and attempt.started_at and submitted_label < attempt.started_at:
            submitted_label = attempt.started_at
        attempt_rows.append({
            'attempt': attempt,
            'duration_label': _format_attempt_duration(attempt.time_spent_seconds),
            'submitted_label': submitted_label,
            'score_label': f"{float(attempt.score or 0):.2f} out of {float(attempt.max_possible_score or 0):.2f} ({float(attempt.score_percentage or 0):.2f}%)",
        })

    question_rows = []
    for question in quiz.questions.prefetch_related('answers').order_by('order'):
        question_rows.append({
            'question': question,
            'answers': list(question.answers.all().order_by('order')),
        })

    can_take_quiz = bool(
        quiz.is_published and
        quiz.total_questions > 0 and
        question_rows and
        (attempts_left > 0 or active_attempt is not None)
    )
    show_take_form = request.GET.get('take') == '1' and can_take_quiz

    context = {
        'course': course,
        'quiz': quiz,
        'attempt_rows': attempt_rows,
        'attempts_allowed': attempts_allowed,
        'attempts_left': attempts_left,
        'final_grade': final_grade,
        'final_percentage': round(final_percentage, 2),
        'question_rows': question_rows,
        'can_take_quiz': can_take_quiz,
        'show_take_form': show_take_form,
        'active_attempt': active_attempt,
    }
    return render(request, 'dashboard/student/quiz_attempts.html', context)


def student_quiz_review(request, attempt_id):
    """Student question-by-question quiz review page."""
    if not request.user.is_authenticated:
        return redirect('custom_login')
    if request.user.role != 'STUDENT':
        return render(request, 'dashboard/unauthorized.html')

    attempt = get_object_or_404(
        QuizAttempt.objects.select_related('quiz', 'quiz__lesson', 'quiz__lesson__module', 'quiz__lesson__module__course'),
        id=attempt_id,
        student=request.user,
    )
    quiz = attempt.quiz
    course = quiz.lesson.module.course
    if not Enrollment.objects.filter(
        student=request.user,
        course=course,
        status=Enrollment.Status.ACTIVE,
    ).exists():
        return render(request, 'dashboard/unauthorized.html')

    questions = list(quiz.questions.prefetch_related('answers').order_by('order'))
    rows = []
    nav_rows = []
    totals = {'correct': 0, 'incorrect': 0, 'unanswered': 0}

    for idx, question in enumerate(questions, start=1):
        answers = list(question.answers.all().order_by('order'))
        response_value = attempt.responses.get(str(question.id))
        selected_answer_id = '' if response_value in [None, ''] else str(response_value)
        correct_answer = next((ans for ans in answers if ans.is_correct), None)
        correct_text = correct_answer.text if correct_answer else (question.correct_answer or '')

        is_answered = response_value not in [None, '']
        is_correct = bool(
            is_answered and correct_answer and str(correct_answer.id) == selected_answer_id
        )
        if question.question_type == Question.QuestionType.TRUE_FALSE and is_answered:
            is_correct = str(response_value).strip().lower() == str(question.correct_answer or '').strip().lower()
        if not is_answered:
            status_key = 'unanswered'
            totals['unanswered'] += 1
        elif is_correct:
            status_key = 'correct'
            totals['correct'] += 1
        else:
            status_key = 'incorrect'
            totals['incorrect'] += 1

        options = []
        selected_answer_text = str(response_value) if is_answered else ''
        for answer in answers:
            option_is_selected = str(answer.id) == selected_answer_id
            option_is_correct = bool(answer.is_correct)
            if option_is_selected:
                selected_answer_text = answer.text
            options.append({
                'text': answer.text,
                'is_selected': option_is_selected,
                'is_correct': option_is_correct,
                'choice_letter': chr(96 + (len(options) + 1)),  # a,b,c...
            })

        rows.append({
            'index': idx,
            'question': question,
            'options': options,
            'status_key': status_key,
            'selected_answer_text': selected_answer_text,
            'correct_answer_text': correct_text,
        })
        nav_rows.append({
            'index': idx,
            'status_key': status_key,
        })

    context = {
        'attempt': attempt,
        'quiz': quiz,
        'course': course,
        'duration_label': _format_attempt_duration(attempt.time_spent_seconds),
        'rows': rows,
        'nav_rows': nav_rows,
        'totals': totals,
        'score_label': f"{float(attempt.score or 0):.2f} out of {float(attempt.max_possible_score or 0):.2f} ({float(attempt.score_percentage or 0):.2f}%)",
    }
    return render(request, 'dashboard/student/quiz_review.html', context)


def _build_risk_explainability(enrollment: Enrollment) -> Dict[str, Any]:
    """
    Build transparent risk-factor breakdown using the same weights as RiskEngine.
    """
    progress_pct = float(enrollment.progress_percentage or 0)
    quiz_pct = float(enrollment.average_quiz_score or 0)
    days_inactive = max(0, int(enrollment.days_since_last_activity or 0))

    progress_risk = max(0.0, min(1.0, 1.0 - (progress_pct / 100.0)))
    quiz_risk = max(0.0, min(1.0, 1.0 - (quiz_pct / 100.0)))
    inactivity_risk = max(0.0, min(1.0, days_inactive / 14.0))

    factors = [
        {
            'name': 'Progress Deficit',
            'weight': 0.40,
            'value_display': f"{progress_pct:.1f}%",
            'risk_component': progress_risk,
            'contribution_pct': progress_risk * 40.0,
        },
        {
            'name': 'Quiz Performance Deficit',
            'weight': 0.40,
            'value_display': f"{quiz_pct:.1f}%",
            'risk_component': quiz_risk,
            'contribution_pct': quiz_risk * 40.0,
        },
        {
            'name': 'Inactivity',
            'weight': 0.20,
            'value_display': f"{days_inactive} days",
            'risk_component': inactivity_risk,
            'contribution_pct': inactivity_risk * 20.0,
        },
    ]
    primary = max(factors, key=lambda item: item['contribution_pct'])
    score_pct = float(enrollment.risk_score or 0) * 100.0
    return {
        'score_pct': round(score_pct, 1),
        'level': enrollment.risk_level,
        'factors': factors,
        'primary_factor': primary['name'],
        'primary_contribution_pct': round(primary['contribution_pct'], 1),
    }


def _recommended_teacher_action(enrollment: Enrollment, explainability: Dict[str, Any]) -> str:
    """Provide one clear intervention suggestion based on the strongest risk driver."""
    primary_factor = str(explainability.get('primary_factor') or '').lower()
    days_inactive = max(0, int(enrollment.days_since_last_activity or 0))

    if 'inactivity' in primary_factor or days_inactive >= 7:
        return "Send a check-in message and ask what is blocking progress."
    if 'quiz' in primary_factor:
        return "Review weak quiz topics and assign targeted remedial work."
    if 'progress' in primary_factor:
        return "Agree on a catch-up target and follow up after one lesson."
    return "Review activity, then plan a short intervention."


def risk_detail(request, student_id, course_id):
    """Detailed student view for a teacher (risk + performance)"""
    # Check if user is authenticated
    if not request.user.is_authenticated:
        return redirect('custom_login')
    
    # Check role
    if request.user.role != 'TEACHER':
        return render(request, 'dashboard/unauthorized.html')
    
    enrollment = get_object_or_404(
        Enrollment.objects.select_related('student', 'course', 'course__teacher'),
        student_id=student_id,
        course_id=course_id,
        course__teacher=request.user
    )

    total_lessons = Lesson.objects.filter(
        module__course=enrollment.course,
        is_published=True
    ).count()
    completed_lessons = LessonCompletion.objects.filter(
        student=enrollment.student,
        lesson__module__course=enrollment.course
    ).select_related('lesson', 'lesson__module').order_by('-completed_at')

    completed_count = completed_lessons.count()
    attendance_rate = round((completed_count / total_lessons) * 100, 1) if total_lessons > 0 else 0

    quiz_attempts = QuizAttempt.objects.filter(
        student=enrollment.student,
        quiz__lesson__module__course=enrollment.course,
        status='COMPLETED'
    ).select_related('quiz', 'quiz__lesson', 'quiz__lesson__module').order_by('-submitted_at')

    raw_risk_history = list(RiskHistory.objects.filter(
        student=enrollment.student,
        course=enrollment.course
    ).order_by('-calculated_at')[:40])

    last_signature = None
    risk_history = []
    for entry in raw_risk_history:
        signature = (entry.risk_level, round(float(entry.risk_score), 3))
        if signature == last_signature:
            continue
        last_signature = signature
        risk_history.append(entry)
        if len(risk_history) >= 20:
            break

    latest_risk_entry = risk_history[0] if risk_history else None

    alerts = Alert.objects.filter(
        teacher=request.user,
        student=enrollment.student,
        course=enrollment.course,
        alert_type__in=RISK_ALERT_TYPES
    ).order_by('-generated_at')[:10]

    risk_explainability = _build_risk_explainability(enrollment)
    latest_risk_factors = latest_risk_entry.contributing_factors if latest_risk_entry else []
    if isinstance(latest_risk_factors, dict):
        latest_risk_factors = list(latest_risk_factors.values())
    if not isinstance(latest_risk_factors, list):
        latest_risk_factors = []
    teacher_action = _recommended_teacher_action(enrollment, risk_explainability)

    context = {
        'teacher_name': request.user.display_name,
        'enrollment': enrollment,
        'total_lessons': total_lessons,
        'completed_count': completed_count,
        'attendance_rate': attendance_rate,
        'completed_lessons': completed_lessons[:20],
        'quiz_attempts': quiz_attempts[:20],
        'risk_history': risk_history,
        'latest_risk_factors': latest_risk_factors,
        'risk_explainability': risk_explainability,
        'teacher_action': teacher_action,
        'alerts': alerts,
    }
    return render(request, 'dashboard/teacher/student_detail.html', context)


def alerts_center(request):
    """Alert management center for teachers"""
    # Check if user is authenticated
    if not request.user.is_authenticated:
        return redirect('custom_login')
    
    # Check role
    if request.user.role != 'TEACHER':
        return render(request, 'dashboard/unauthorized.html')
    
    courses = Course.objects.filter(teacher=request.user).order_by('title')
    context = {
        'teacher_name': request.user.display_name,
        'courses': courses,
    }
    return render(request, 'dashboard/teacher/alerts.html', context)


def export_students_csv(enrollments):
    """Export student data to CSV"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="students_data.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Student Name', 'Email', 'Course', 'Progress (%)', 'Quiz Average (%)', 
        'Risk Level', 'Engagement', 'Last Activity', 'Days Since Activity'
    ])
    
    for enrollment in enrollments:
        writer.writerow([
            enrollment.student.display_name,
            enrollment.student.email,
            enrollment.course.title,
            f"{enrollment.progress_percentage:.1f}",
            f"{enrollment.average_quiz_score:.1f}",
            enrollment.risk_level,
            'High' if enrollment.engagement_score >= 0.8 else 'Medium' if enrollment.engagement_score >= 0.5 else 'Low',
            enrollment.last_activity.strftime('%Y-%m-%d %H:%M') if enrollment.last_activity else '',
            enrollment.days_since_last_activity,
        ])
    
    return response


def teacher_students(request):
    """Teacher view listing all students in the teacher's courses"""
    if not request.user.is_authenticated:
        return redirect('custom_login')

    if request.user.role != 'TEACHER':
        return render(request, 'dashboard/unauthorized.html')

    enrollments = Enrollment.objects.filter(
        course__teacher=request.user
    ).select_related('student', 'course').order_by('-last_activity', 'student__display_name')

    # Filter by course
    course_id = request.GET.get('course')
    if course_id:
        enrollments = enrollments.filter(course_id=course_id)
    
    # Search by student name or email
    search_query = request.GET.get('search', '').strip()
    if search_query:
        from django.db.models import Q
        enrollments = enrollments.filter(
            Q(student__display_name__icontains=search_query) |
            Q(student__email__icontains=search_query)
        )

    # Handle CSV export
    if request.GET.get('export') == 'csv':
        return export_students_csv(enrollments)

    # Enrich enrollments with risk contribution data
    for enrollment in enrollments:
        explanation = _build_risk_explainability(enrollment)
        factor_map = {item['name']: item['contribution_pct'] for item in explanation['factors']}
        progress_contribution = factor_map.get('Progress Deficit', 0.0)
        quiz_contribution = factor_map.get('Quiz Performance Deficit', 0.0)
        inactivity_contribution = factor_map.get('Inactivity', 0.0)
        days_inactive = enrollment.days_since_last_activity or 0
        enrollment.risk_score_pct = explanation['score_pct']
        enrollment.primary_factor = explanation['primary_factor']
        enrollment.teacher_action = _recommended_teacher_action(enrollment, explanation)
        enrollment.risk_tooltip = (
            f"Risk Score: {explanation['score_pct']:.1f}% | "
            f"Primary Factor: {explanation['primary_factor']} ({explanation['primary_contribution_pct']:.1f}% impact) | "
            f"Progress: {enrollment.progress_percentage:.0f}% (weight 40%, contributes {progress_contribution:.1f}%) | "
            f"Quiz: {enrollment.average_quiz_score:.0f}% (weight 40%, contributes {quiz_contribution:.1f}%) | "
            f"Inactivity: {days_inactive}d (weight 20%, contributes {inactivity_contribution:.1f}%)"
        )

    courses = Course.objects.filter(
        teacher=request.user
    ).order_by('title')

    context = {
        'teacher_name': request.user.display_name,
        'enrollments': enrollments,
        'courses': courses,
        'selected_course_id': course_id or '',
        'search_query': search_query,
    }
    return render(request, 'dashboard/teacher/students.html', context)


def student_enroll_by_key(request):
    """Allow a student to enroll in a published course using enrollment key."""
    if not request.user.is_authenticated:
        return redirect('custom_login')
    if request.user.role != 'STUDENT':
        return render(request, 'dashboard/unauthorized.html')

    if request.method != 'POST':
        return redirect('student_dashboard')

    key = (request.POST.get('enrollment_key', '') or '').strip().upper()
    next_url = request.POST.get('next_url') or request.META.get('HTTP_REFERER') or reverse('student_dashboard')

    if not key:
        messages.error(request, 'Please enter an enrollment key.')
        return redirect(next_url)

    course = Course.objects.filter(
        enrollment_key=key,
        status=Course.Status.PUBLISHED
    ).first()
    if not course:
        messages.error(request, 'Invalid key or course is not currently open for enrollment.')
        return redirect(next_url)

    enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
    if enrollment:
        if enrollment.status != Enrollment.Status.ACTIVE:
            enrollment.status = Enrollment.Status.ACTIVE
            enrollment.save(update_fields=['status'])
            messages.success(request, f'Re-enrolled in {course.title} successfully.')
        else:
            messages.info(request, f'You are already enrolled in {course.title}.')
        return redirect(next_url)

    Enrollment.objects.create(
        student=request.user,
        course=course,
        status=Enrollment.Status.ACTIVE
    )
    messages.success(request, f'Successfully enrolled in {course.title}.')
    return redirect(next_url)


def teacher_payments(request):
    """Teacher view for payment status of enrolled students."""
    if not request.user.is_authenticated:
        return redirect('custom_login')

    if request.user.role != 'TEACHER':
        return render(request, 'dashboard/unauthorized.html')

    def _read_filters(data):
        course_val = (data.get('course', '') or '').strip()
        payment_val = (data.get('payment', 'all') or 'all').strip().lower()
        search_val = (data.get('search', '') or '').strip()
        if payment_val not in {'all', 'paid', 'unpaid'}:
            payment_val = 'all'
        return course_val, payment_val, search_val

    def _build_queryset(course_val='', payment_val='all', search_val=''):
        qs = Enrollment.objects.filter(
            course__teacher=request.user,
            status='ACTIVE'
        ).select_related('student', 'course').order_by('student__display_name', 'course__title')

        if course_val:
            qs = qs.filter(course_id=course_val)

        if search_val:
            qs = qs.filter(
                Q(student__display_name__icontains=search_val)
                | Q(student__email__icontains=search_val)
                | Q(student__username__icontains=search_val)
            )

        if payment_val == 'paid':
            qs = qs.filter(is_fee_paid=True)
        elif payment_val == 'unpaid':
            qs = qs.filter(is_fee_paid=False)

        return qs

    if request.method == 'POST':
        enrollment_id = request.POST.get('enrollment_id')
        payment_action = request.POST.get('payment_action')
        course_qs, payment_qs, search_qs = _read_filters(request.POST)

        if payment_action == 'send_unpaid_notifications':
            filtered_qs = _build_queryset(course_qs, 'all', search_qs)
            unpaid_qs = filtered_qs.filter(is_fee_paid=False)
            sent_count = 0
            for enrollment in unpaid_qs:
                existing = Alert.objects.filter(
                    teacher=request.user,
                    student=enrollment.student,
                    course=enrollment.course,
                    enrollment=enrollment,
                    alert_type=Alert.AlertType.CUSTOM,
                    status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED],
                    title='Payment Reminder'
                ).exists()
                if existing:
                    continue

                Alert.objects.create(
                    teacher=request.user,
                    student=enrollment.student,
                    course=enrollment.course,
                    enrollment=enrollment,
                    alert_type=Alert.AlertType.CUSTOM,
                    severity=Alert.Severity.MEDIUM,
                    title='Payment Reminder',
                    message=f'Please clear your course payment for {enrollment.course.title}.',
                    recommendation='Settle outstanding fee and contact your teacher if you need support.'
                )
                sent_count += 1

            messages.success(request, f'Sent {sent_count} payment notification(s) to unpaid students.')
        else:
            enrollment = Enrollment.objects.filter(
                id=enrollment_id,
                course__teacher=request.user
            ).first()

            if not enrollment:
                messages.error(request, 'Enrollment not found.')
            else:
                enrollment.is_fee_paid = payment_action == 'mark_paid'
                enrollment.save(update_fields=['is_fee_paid'])
                state = 'paid' if enrollment.is_fee_paid else 'not paid'
                messages.success(request, f'Updated payment status to {state} for {enrollment.student.display_name}.')

        redirect_url = reverse('teacher_payments')
        query_params = {}
        if course_qs:
            query_params['course'] = course_qs
        if payment_qs and payment_qs != 'all':
            query_params['payment'] = payment_qs
        if search_qs:
            query_params['search'] = search_qs
        if query_params:
            redirect_url = f"{redirect_url}?{urlencode(query_params)}"
        return redirect(redirect_url)

    course_id, payment_filter, search_query = _read_filters(request.GET)
    enrollments = _build_queryset(course_id, payment_filter, search_query)

    if request.GET.get('export', '').strip().lower() == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payments_report.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Student Name', 'Email', 'Username', 'Course', 'Payment Status',
            'Progress %', 'Average Quiz %', 'Risk Level', 'Last Activity', 'Enrolled At'
        ])
        for enrollment in enrollments:
            writer.writerow([
                enrollment.student.display_name,
                enrollment.student.email,
                enrollment.student.username,
                enrollment.course.title,
                'Paid' if enrollment.is_fee_paid else 'Not Paid',
                float(enrollment.progress_percentage),
                float(enrollment.average_quiz_score),
                enrollment.risk_level,
                enrollment.last_activity.strftime('%Y-%m-%d %H:%M:%S') if enrollment.last_activity else '',
                enrollment.enrolled_at.strftime('%Y-%m-%d %H:%M:%S') if enrollment.enrolled_at else '',
            ])
        return response

    summary_base = Enrollment.objects.filter(
        course__teacher=request.user,
        status='ACTIVE'
    )

    courses = Course.objects.filter(teacher=request.user).order_by('title')
    course_options = [{'id': str(course.id), 'title': course.title} for course in courses]

    context = {
        'enrollments': enrollments,
        'courses': course_options,
        'selected_course_id': course_id,
        'selected_payment_filter': payment_filter,
        'search_query': search_query,
        'paid_count': summary_base.filter(is_fee_paid=True).count(),
        'unpaid_count': summary_base.filter(is_fee_paid=False).count(),
        'total_count': summary_base.count(),
    }
    return render(request, 'dashboard/teacher/payments.html', context)


def admin_dashboard(request):
    """System-wide dashboard for staff/admin users"""
    if not request.user.is_authenticated:
        return redirect('custom_login')

    if not (request.user.is_staff or request.user.is_superuser):
        return render(request, 'dashboard/unauthorized.html')

    User = get_user_model()

    users_qs = User.objects.all()
    courses_qs = Course.objects.all()
    enrollments_qs = Enrollment.objects.all()
    alerts_qs = Alert.objects.all()

    last_24_hours = timezone.now() - timedelta(hours=24)

    teachers_using_system = users_qs.filter(
        role='TEACHER',
        courses_teaching__isnull=False
    ).annotate(
        total_courses=Count('courses_teaching', distinct=True),
        total_enrollments=Count('courses_teaching__enrollments', distinct=True)
    ).order_by('-last_activity', 'display_name')

    enrolled_students = users_qs.filter(
        role='STUDENT',
        enrollments__status='ACTIVE'
    ).annotate(
        active_courses=Count('enrollments', filter=Q(enrollments__status='ACTIVE'), distinct=True),
        avg_quiz=Avg('enrollments__average_quiz_score')
    ).order_by('-last_activity', 'display_name')

    context = {
        'total_users': users_qs.count(),
        'total_teachers': users_qs.filter(role='TEACHER').count(),
        'total_students': users_qs.filter(role='STUDENT').count(),
        'published_courses': courses_qs.filter(status='PUBLISHED').count(),
        'active_enrollments': enrollments_qs.filter(status='ACTIVE').count(),
        'active_alerts': alerts_qs.filter(status='ACTIVE').count(),
        'resolved_alerts': alerts_qs.filter(status='RESOLVED').count(),
        'quiz_attempts_24h': QuizAttempt.objects.filter(
            status='COMPLETED',
            submitted_at__gte=last_24_hours
        ).count(),
        'teachers_using_system': teachers_using_system[:20],
        'enrolled_students': enrolled_students[:30],
        'recent_users': users_qs.order_by('-date_joined')[:8],
        'recent_alerts': alerts_qs.select_related('student', 'teacher', 'course').order_by('-generated_at')[:8],
    }
    return render(request, 'dashboard/admin/dashboard.html', context)

# ============================================
# API VIEWS (JSON endpoints for charts)
# ============================================

class TeacherDashboardAPI(APIView):
    """
    API endpoints for teacher dashboard data
    """
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    
    def get(self, request, format=None):
        """Get all dashboard data in one request"""
        teacher = request.user

        # Recompute risk and alerts to avoid stale UB: ensure dashboard summary is consistent.
        AlertGenerator.check_and_generate_alerts(recalculate_risk=True, course_id=None)

        # Keep unresolved alerts aligned with latest enrollment risk state.
        AlertGenerator._resolve_old_alerts()

        # Provide CSV export endpoint for teacher sharing (My Students export requirement).
        if request.query_params.get('export') == 'csv':
            # Export all active enrollments for the teacher's courses.
            courses = Course.objects.filter(teacher=teacher, status='PUBLISHED')
            course_ids = courses.values_list('id', flat=True)
            enrollments = Enrollment.objects.filter(course_id__in=course_ids, status='ACTIVE').select_related('student', 'course')

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="teachlink_my_students.csv"'

            writer = csv.writer(response)
            writer.writerow([
                'Student', 'Course', 'Risk Level', 'Risk Score (%)', 'Progress (%)', 'Average Quiz (%)',
                'Engagement (%)', 'Last Active', 'Pending Assessments', 'Active Alerts'
            ])

            for e in enrollments:
                pending_assessments = Quiz.objects.filter(
                    lesson__module__course=e.course,
                    is_published=True,
                    total_questions__gt=0
                ).count() - QuizAttempt.objects.filter(
                    student=e.student,
                    quiz__lesson__module__course=e.course,
                    status__in=[QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT]
                ).values('quiz_id').distinct().count()
                active_alerts = Alert.objects.filter(student=e.student, course=e.course, status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED]).count()

                writer.writerow([
                    e.student.display_name,
                    e.course.title,
                    e.risk_level,
                    round(float(e.risk_score or 0) * 100, 1),
                    float(e.progress_percentage or 0),
                    float(e.average_quiz_score or 0),
                    round(float(e.engagement_score or 0) * 100, 1),
                    e.last_activity.isoformat() if e.last_activity else '',
                    pending_assessments,
                    active_alerts,
                ])

            return response
        
        # Get teacher's courses
        courses = Course.objects.filter(teacher=teacher, status='PUBLISHED')
        course_ids = courses.values_list('id', flat=True)
        
        # Get active enrollments
        enrollments = Enrollment.objects.filter(
            course_id__in=course_ids,
            status='ACTIVE'
        ).select_related('student', 'course')
        
        # Calculate KPIs
        total_students = enrollments.count()
        high_risk_count = enrollments.filter(risk_level__in=['HIGH', 'CRITICAL']).count()
        medium_risk_count = enrollments.filter(risk_level='MEDIUM').count()
        low_risk_count = enrollments.filter(risk_level='LOW').count()
        
        # Average performance
        avg_performance = enrollments.aggregate(
            avg=Avg('average_quiz_score')
        )['avg'] or 0

        score_bands = {
            'Below 40%': 0,
            '40-59%': 0,
            '60-79%': 0,
            '80%+': 0,
        }
        focus_students = []
        ranked_enrollments = sorted(
            list(enrollments),
            key=lambda item: (float(item.risk_score or 0), -(float(item.progress_percentage or 0))),
            reverse=True,
        )
        for enrollment in ranked_enrollments:
            avg_score_value = float(enrollment.average_quiz_score or 0)
            if avg_score_value < 40:
                score_bands['Below 40%'] += 1
            elif avg_score_value < 60:
                score_bands['40-59%'] += 1
            elif avg_score_value < 80:
                score_bands['60-79%'] += 1
            else:
                score_bands['80%+'] += 1

        for enrollment in ranked_enrollments[:5]:
            explainability = _build_risk_explainability(enrollment)
            focus_students.append({
                'student_id': str(enrollment.student_id),
                'course_id': str(enrollment.course_id),
                'student_name': enrollment.student.display_name,
                'course_title': enrollment.course.title,
                'risk_level': enrollment.risk_level,
                'risk_score_pct': explainability['score_pct'],
                'primary_factor': explainability['primary_factor'],
                'progress': float(enrollment.progress_percentage or 0),
                'avg_quiz': float(enrollment.average_quiz_score or 0),
                'days_inactive': int(enrollment.days_since_last_activity or 0),
                'recommended_action': _recommended_teacher_action(enrollment, explainability),
                'detail_url': reverse(
                    'teacher_student_detail',
                    kwargs={'student_id': enrollment.student_id, 'course_id': enrollment.course_id}
                ),
            })

        # Refresh lesson difficulty snapshots so labels and failure rates stay in sync.
        for course in courses:
            DifficultyAnalyzer.analyze_course_difficulties(str(course.id))
        
        unresolved_alerts = Alert.objects.filter(
            teacher=teacher,
            status__in=['ACTIVE', 'ACKNOWLEDGED'],
            alert_type__in=RISK_ALERT_TYPES
        )
        active_alerts_count = unresolved_alerts.count()
        recent_alerts = unresolved_alerts.select_related('student', 'course').order_by('-generated_at')[:10]
        
        # Risk distribution by course
        course_risk = []
        for course in courses[:5]:  # Top 5 courses
            course_enrollments = enrollments.filter(course=course)
            if course_enrollments.exists():
                course_risk.append({
                    'course_id': str(course.id),
                    'course_title': course.title,
                    'total': course_enrollments.count(),
                    'high_risk': course_enrollments.filter(
                        risk_level__in=['HIGH', 'CRITICAL']
                    ).count(),
                    'medium_risk': course_enrollments.filter(risk_level='MEDIUM').count(),
                    'low_risk': course_enrollments.filter(risk_level='LOW').count(),
                })
        
        # Hardest topics
        hardest_topics = LessonDifficulty.objects.filter(
            lesson__module__course__teacher=teacher
        ).select_related('lesson__module__course').order_by('-difficulty_score')[:10]
        
        # Format alert data
        alerts_data = []
        for alert in recent_alerts:
            alerts_data.append({
                'id': str(alert.id),
                'student_name': alert.student.display_name,
                'course_title': alert.course.title if alert.course else 'N/A',
                'alert_type': alert.get_alert_type_display(),
                'severity': alert.severity,
                'title': alert.title,
                'message': alert.message,
                'recommendation': alert.recommendation or 'Review the student detail view and intervene.',
                'generated_at': alert.generated_at.isoformat(),
                'status': alert.status,
            })
        
        # Format topics data
        topics_data = []
        for topic in hardest_topics:
            signal = f"{round(float(topic.failure_rate or 0) * 100)}% failed, {int(topic.total_views or 0)} views"
            topics_data.append({
                'lesson_id': str(topic.lesson.id),
                'lesson_title': topic.lesson.title,
                'course_title': topic.lesson.module.course.title,
                'difficulty_score': float(topic.difficulty_score),
                'difficulty_level': topic.difficulty_level,
                'difficulty_label': difficulty_display_label(topic.difficulty_level),
                'failure_rate': float(topic.failure_rate),
                'access_count': topic.total_views,
                'signal': signal,
            })
        
        return Response({
            'kpi': {
                'total_students': total_students,
                'high_risk_count': high_risk_count,
                'medium_risk_count': medium_risk_count,
                'low_risk_count': low_risk_count,
                'avg_performance': round(avg_performance, 1),
                'active_alerts': active_alerts_count,
            },
            'risk_distribution': {
                'labels': ['Low Risk', 'Medium Risk', 'High Risk'],
                'data': [low_risk_count, medium_risk_count, high_risk_count],
                'colors': ['#10b981', '#f59e0b', '#ef4444'],
            },
            'score_distribution': {
                'labels': list(score_bands.keys()),
                'data': list(score_bands.values()),
                'colors': ['#dc2626', '#f59e0b', '#0ea5e9', '#10b981'],
            },
            'risk_engine_summary': {
                'formula': 'Risk Score = 40% progress deficit + 40% quiz performance deficit + 20% inactivity',
                'students_requiring_attention': high_risk_count + medium_risk_count,
                'highest_risk_score_pct': round(float(ranked_enrollments[0].risk_score or 0) * 100, 1) if ranked_enrollments else 0.0,
            },
            'course_risk': course_risk,
            'recent_alerts': alerts_data,
            'hardest_topics': topics_data,
            'focus_students': focus_students,
        })

    

class StudentDashboardAPI(APIView):
    """
    API endpoints for student dashboard data
    """
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request, format=None):
        """Get student's dashboard data"""
        student = request.user

        enrollments = list(
            Enrollment.objects.filter(
                student=student,
                status='ACTIVE'
            ).select_related('course').order_by('course__title')
        )

        if enrollments:
            total_progress = sum(float(e.progress_percentage or 0) for e in enrollments) / len(enrollments)
        else:
            total_progress = 0.0

        recent_attempts = list(
            QuizAttempt.objects.filter(
                student=student,
                status__in=[QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT],
                submitted_at__isnull=False,
            ).select_related(
                'quiz',
                'quiz__lesson',
                'quiz__lesson__module',
                'quiz__lesson__module__course',
            ).order_by('-submitted_at')[:20]
        )

        courses_data = []
        for enrollment in enrollments:
            next_lesson = self._get_next_lesson(enrollment)
            published_quiz_ids = list(
                Quiz.objects.filter(
                    lesson__module__course=enrollment.course,
                    is_published=True,
                ).values_list('id', flat=True)
            )
            attempted_quiz_ids = set(
                QuizAttempt.objects.filter(
                    student=student,
                    quiz_id__in=published_quiz_ids,
                    status__in=[QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT],
                    submitted_at__isnull=False,
                ).values_list('quiz_id', flat=True).distinct()
            ) if published_quiz_ids else set()
            recent_quizzes = QuizAttempt.objects.filter(
                student=student,
                quiz__lesson__module__course=enrollment.course,
                status__in=[QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT],
                submitted_at__isnull=False,
            ).order_by('-submitted_at')[:5]
            failed_attempts_count = QuizAttempt.objects.filter(
                student=student,
                quiz__lesson__module__course=enrollment.course,
                status__in=[QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT],
                passed=False,
            ).count()

            expected_progress = self._estimate_expected_progress(enrollment)
            progress_gap = None
            if expected_progress is not None:
                progress_gap = round(expected_progress - float(enrollment.progress_percentage or 0), 1)

            courses_data.append({
                'enrollment_id': str(enrollment.id),
                'course_id': str(enrollment.course.id),
                'course_title': enrollment.course.title,
                'progress': float(enrollment.progress_percentage or 0),
                'avg_score': float(enrollment.average_quiz_score or 0),
                'risk_level': enrollment.risk_level,
                'risk_score': float(enrollment.risk_score or 0),
                'risk_explainability': _build_risk_explainability(enrollment),
                'engagement_score': float(enrollment.engagement_score or 0),
                'engagement_level': self._engagement_level(float(enrollment.engagement_score or 0)),
                'last_activity': enrollment.last_activity.isoformat(),
                'next_lesson': next_lesson,
                'course_assessment_url': reverse('student_course_quizzes', kwargs={'course_id': enrollment.course.id}),
                'my_course_url': f"{reverse('dashboard_courses')}#course-{enrollment.course.id}",
                'expected_progress': expected_progress,
                'progress_gap': progress_gap,
                'days_inactive': int(enrollment.days_since_last_activity or 0),
                'pending_assessments_count': max(0, len(published_quiz_ids) - len(attempted_quiz_ids)),
                'failed_attempts_count': failed_attempts_count,
                'recent_quiz_scores': [
                    {
                        'quiz_id': str(a.quiz.id),
                        'quiz_title': a.quiz.title,
                        'score': self._normalize_percentage(float(a.score_percentage or 0)),
                        'passed': bool(a.passed),
                        'status': a.status,
                        'date': a.submitted_at.isoformat() if a.submitted_at else None,
                    }
                    for a in recent_quizzes
                ],
            })

        thirty_days_ago = timezone.now() - timedelta(days=30)
        trend_attempts = [
            attempt for attempt in reversed(recent_attempts)
            if attempt.status == QuizAttempt.Status.COMPLETED and attempt.submitted_at and attempt.submitted_at >= thirty_days_ago
        ]
        if not trend_attempts:
            trend_attempts = [
                attempt for attempt in reversed(recent_attempts)
                if attempt.status == QuizAttempt.Status.COMPLETED and attempt.submitted_at
            ]

        performance_trend = []
        for attempt in trend_attempts:
            performance_trend.append({
                'date': attempt.submitted_at.date().isoformat(),
                'timestamp': attempt.submitted_at.isoformat(),
                'score': round(self._normalize_percentage(float(attempt.score_percentage or 0)), 2),
                'quiz': attempt.quiz.title,
                'course_title': attempt.quiz.lesson.module.course.title,
            })

        upcoming = []
        for enrollment in enrollments:
            if not enrollment.course.end_date:
                continue
            days_left = (enrollment.course.end_date - timezone.now().date()).days
            if 0 <= days_left <= 14:
                upcoming.append({
                    'course_id': str(enrollment.course.id),
                    'course_title': enrollment.course.title,
                    'deadline': enrollment.course.end_date.isoformat(),
                    'days_left': days_left,
                    'current_progress': float(enrollment.progress_percentage or 0),
                    'expected_progress': self._estimate_expected_progress(enrollment),
                })
        upcoming.sort(key=lambda row: row['days_left'])

        _resolve_stale_payment_reminders(student)
        _collapse_student_alert_duplicates(student)
        notifications_base = Alert.objects.filter(
            student=student,
            status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED]
        ).select_related('teacher', 'course')
        unread_count = _deduped_unread_count(student)
        notifications_source = list(notifications_base.order_by('-generated_at')[:120])
        notifications_qs, suppressed_count = _dedupe_student_notifications(notifications_source, limit=10)

        notifications = [
            {
                'id': str(alert.id),
                'title': alert.title,
                'message': alert.message,
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'status': alert.status,
                'course_title': alert.course.title if alert.course else 'N/A',
                'teacher_name': alert.teacher.display_name,
                'generated_at': alert.generated_at.isoformat(),
            }
            for alert in notifications_qs
        ]

        best_by_quiz = {
            str(item['quiz_id']): self._normalize_percentage(float(item['best_score'] or 0))
            for item in QuizAttempt.objects.filter(
                student=student,
                quiz_id__in=[a.quiz_id for a in recent_attempts],
                status__in=[QuizAttempt.Status.COMPLETED, QuizAttempt.Status.TIMED_OUT],
            ).values('quiz_id').annotate(best_score=Max('score_percentage'))
        } if recent_attempts else {}

        recent_attempt_cards = []
        for attempt in recent_attempts[:8]:
            quiz_id = str(attempt.quiz.id)
            recent_attempt_cards.append({
                'quiz_id': quiz_id,
                'quiz_title': attempt.quiz.title,
                'course_title': attempt.quiz.lesson.module.course.title,
                'score': round(self._normalize_percentage(float(attempt.score_percentage or 0)), 2),
                'best_score': round(float(best_by_quiz.get(quiz_id, 0.0)), 2),
                'passed': bool(attempt.passed),
                'status': attempt.status,
                'date': attempt.submitted_at.isoformat() if attempt.submitted_at else None,
            })

        encouragement = self._get_encouragement_message(total_progress)
        next_steps = self._build_next_steps(courses_data, upcoming, recent_attempt_cards)
        risk_priority = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, 'UNKNOWN': 0}
        focus_course = None
        if courses_data:
            focus_course = sorted(
                courses_data,
                key=lambda c: (
                    risk_priority.get((c.get('risk_level') or 'UNKNOWN').upper(), 0),
                    float(c.get('progress_gap') or 0),
                    float(c.get('risk_score') or 0),
                ),
                reverse=True,
            )[0]

        average_engagement_score = (
            sum(float(course.get('engagement_score') or 0) for course in courses_data) / len(courses_data)
            if courses_data else
            0.0
        )
        pending_assessments_total = sum(int(course.get('pending_assessments_count') or 0) for course in courses_data)
        focus_status = {}
        if focus_course:
            explainability = focus_course.get('risk_explainability') or {}
            inactivity_factor = next(
                (factor for factor in explainability.get('factors', []) if factor.get('name') == 'Inactivity'),
                None
            )
            days_inactive_count = int(focus_course.get('days_inactive') or 0)
            pending_assessments = int(focus_course.get('pending_assessments_count') or 0)
            failed_attempts = int(focus_course.get('failed_attempts_count') or 0)
            progress_gap = round(float(focus_course.get('progress_gap') or 0), 1)
            primary_factor = explainability.get('primary_factor') or "Risk factors still updating"
            if progress_gap > 5:
                next_action = f"Complete '{focus_course['next_lesson']['title']}' to reduce your progress gap." if focus_course.get('next_lesson') else "Complete one lesson today to reduce your progress gap."
            elif pending_assessments > 0:
                next_action = f"Take {pending_assessments} pending assessment{'s' if pending_assessments != 1 else ''} in {focus_course['course_title']}."
            elif failed_attempts > 0:
                next_action = f"Review the quiz topics you missed in {focus_course['course_title']}."
            elif focus_course.get('next_lesson'):
                next_action = f"Continue '{focus_course['next_lesson']['title']}' in {focus_course['course_title']}."
            else:
                next_action = "Keep your momentum by staying active in your courses."

            summary_bits = [
                f"Risk is {focus_course.get('risk_level', 'UNKNOWN')} ({round(float(focus_course.get('risk_score') or 0) * 100.0, 1)}%).",
                f"Main issue: {str(primary_factor).lower()}.",
            ]
            if pending_assessments > 0:
                summary_bits.append(f"{pending_assessments} assessment{'s' if pending_assessments != 1 else ''} still need attention.")
            if days_inactive_count > 0:
                summary_bits.append(f"Last activity was {days_inactive_count} day{'s' if days_inactive_count != 1 else ''} ago.")

            focus_status = {
                'course_title': focus_course.get('course_title'),
                'risk_level': focus_course.get('risk_level'),
                'risk_score_pct': round(float(focus_course.get('risk_score') or 0) * 100.0, 1),
                'engagement_score_pct': round(float(focus_course.get('engagement_score') or 0) * 100.0, 1),
                'engagement_level': focus_course.get('engagement_level'),
                'primary_factor': primary_factor,
                'days_inactive': inactivity_factor.get('value_display') if inactivity_factor else '0 days',
                'days_inactive_count': days_inactive_count,
                'pending_assessments_count': pending_assessments,
                'failed_attempts_count': failed_attempts,
                'progress_gap': progress_gap,
                'next_lesson': focus_course.get('next_lesson'),
                'course_url': focus_course.get('my_course_url') or focus_course.get('course_assessment_url'),
                'summary_message': " ".join(summary_bits),
                'next_action': next_action,
            }

        return Response({
            'student_name': student.display_name,
            'overall_progress': round(total_progress, 1),
            'enrolled_courses': len(enrollments),
            'pending_assessments_total': pending_assessments_total,
            'courses': courses_data,
            'performance_trend': performance_trend[-20:],
            'recent_quiz_attempts': recent_attempt_cards,
            'upcoming_deadlines': upcoming,
            'unread_count': unread_count,
            'notifications_suppressed_count': suppressed_count,
            'notifications': notifications,
            'encouragement': encouragement,
            'next_steps': next_steps,
            'focus_status': focus_status,
            'overall_engagement_score_pct': round(average_engagement_score * 100.0, 1),
            'overall_engagement_level': self._engagement_level(average_engagement_score),
        })

    def post(self, request, format=None):
        """Handle student actions like reporting difficulty"""
        action = request.data.get('action')
        if action == 'report_difficulty':
            return self._report_difficulty(request)
        return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)

    def _report_difficulty(self, request):
        """Report difficulty to teacher"""
        course_id = request.data.get('course_id')
        lesson_id = request.data.get('lesson_id')
        reason = (request.data.get('reason') or '').strip()

        if not course_id or not reason:
            return Response({'error': 'course_id and reason are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            enrollment = Enrollment.objects.get(
                student=request.user,
                course_id=course_id,
                status='ACTIVE'
            )
        except Enrollment.DoesNotExist:
            return Response({'error': 'Enrollment not found'}, status=status.HTTP_404_NOT_FOUND)

        lesson = None
        if lesson_id:
            lesson = Lesson.objects.filter(
                id=lesson_id,
                module__course=enrollment.course,
                is_published=True
            ).first()
            if not lesson:
                return Response({'error': 'Lesson not found in this course'}, status=status.HTTP_404_NOT_FOUND)

        lesson_context = f' for lesson "{lesson.title}"' if lesson else ''
        recommendation = "Review student's progress and provide additional support."
        if lesson:
            recommendation = f"Review lesson '{lesson.title}' and provide targeted support/resources."

        alert = Alert.objects.create(
            teacher=enrollment.course.teacher,
            student=request.user,
            course=enrollment.course,
            title=f"Difficulty Report from {request.user.display_name}",
            alert_type=Alert.AlertType.PERFORMANCE_DROP,
            severity=Alert.Severity.MEDIUM,
            status=Alert.Status.ACTIVE,
            message=f"Student reported difficulty{lesson_context}: {reason}",
            recommendation=recommendation,
            risk_score=enrollment.risk_score,
            progress_percentage=enrollment.progress_percentage,
        )

        return Response({
            'message': 'Difficulty reported successfully. Your teacher has been notified.',
            'alert_id': str(alert.id),
            'lesson': lesson.title if lesson else None,
        })

    def _get_next_lesson(self, enrollment):
        """Get the next lesson for student to complete"""
        completed = LessonCompletion.objects.filter(
            student=enrollment.student,
            lesson__module__course=enrollment.course
        ).values_list('lesson_id', flat=True)

        next_lesson = Lesson.objects.filter(
            module__course=enrollment.course,
            is_published=True
        ).exclude(
            id__in=completed
        ).order_by('module__order', 'order').first()

        if next_lesson:
            return {
                'id': str(next_lesson.id),
                'title': next_lesson.title,
                'module': next_lesson.module.title,
                'estimated_minutes': next_lesson.estimated_minutes,
                'open_url': reverse('open_lesson_material', kwargs={'lesson_id': next_lesson.id}),
            }
        return None

    def _normalize_percentage(self, score: float) -> float:
        normalized_score = score * 100 if score <= 1 else score
        return max(0.0, min(100.0, normalized_score))

    def _engagement_level(self, score: float) -> str:
        if score >= 0.80:
            return 'HIGH'
        if score >= 0.50:
            return 'MEDIUM'
        return 'LOW'

    def _estimate_expected_progress(self, enrollment: Enrollment) -> Optional[float]:
        course = enrollment.course
        today = timezone.now().date()

        if course.start_date and course.end_date and course.end_date >= course.start_date:
            total_days = (course.end_date - course.start_date).days
            if total_days <= 0:
                return 100.0 if today >= course.end_date else 0.0
            elapsed_days = (today - course.start_date).days
            ratio = max(0.0, min(1.0, elapsed_days / total_days))
            return round(ratio * 100.0, 1)

        if course.end_date and course.end_date >= enrollment.enrolled_at.date():
            total_days = (course.end_date - enrollment.enrolled_at.date()).days
            if total_days <= 0:
                return 100.0 if today >= course.end_date else 0.0
            elapsed_days = (today - enrollment.enrolled_at.date()).days
            ratio = max(0.0, min(1.0, elapsed_days / total_days))
            return round(ratio * 100.0, 1)

        return None

    def _build_next_steps(self, courses_data: List[Dict[str, Any]], upcoming: List[Dict[str, Any]], recent_attempts: List[Dict[str, Any]]) -> List[str]:
        if not courses_data:
            return ["Join a course with an enrollment key to begin your learning journey."]

        risk_priority = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, 'UNKNOWN': 0}
        ranked_courses = sorted(
            courses_data,
            key=lambda c: (
                risk_priority.get((c.get('risk_level') or 'UNKNOWN').upper(), 0),
                float(c.get('progress_gap') or 0),
                -float(c.get('progress') or 0),
            ),
            reverse=True,
        )
        focus_course = ranked_courses[0]

        steps: List[str] = []
        progress_gap = float(focus_course.get('progress_gap') or 0)
        if progress_gap > 5:
            steps.append(
                f"You are {round(progress_gap, 1)}% behind expected progress in {focus_course['course_title']}. Complete one lesson there today."
            )
        else:
            steps.append(
                f"Focus on {focus_course['course_title']} today to keep your progress steady."
            )

        if focus_course.get('next_lesson'):
            lesson = focus_course['next_lesson']
            steps.append(f"Continue '{lesson.get('title', 'next lesson')}' in {focus_course['course_title']}.")

        explain = focus_course.get('risk_explainability') or {}
        primary = explain.get('primary_factor')
        if primary:
            steps.append(
                f"Main risk factor in {focus_course['course_title']}: {str(primary).lower()}."
            )

        matching_deadline = next((d for d in upcoming if d.get('course_title') == focus_course.get('course_title')), None)
        if matching_deadline:
            steps.append(f"Deadline in {focus_course['course_title']}: {matching_deadline['days_left']} day(s) left.")

        if not recent_attempts:
            steps.append(f"Take a quiz in {focus_course['course_title']} to refresh your performance data.")

        return steps[:4]

    def _get_encouragement_message(self, progress):
        """Generate encouragement message based on progress"""
        if progress >= 80:
            return {
                'message': "Outstanding progress! You're almost there. Keep up the great work!",
                'icon': 'trophy',
                'color': 'gold',
            }
        elif progress >= 50:
            return {
                'message': "You're making solid progress. Stay consistent and you'll reach your goals!",
                'icon': 'trending-up',
                'color': 'green',
            }
        elif progress >= 25:
            return {
                'message': "Good start! Every lesson completed is a step forward. You've got this!",
                'icon': 'thumbs-up',
                'color': 'blue',
            }
        else:
            return {
                'message': "Ready to begin your learning journey? Let's make progress together!",
                'icon': 'rocket',
                'color': 'purple',
            }


class StudentNotificationAPI(APIView):
    """Student notification actions such as marking as read."""
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request, format=None):
        alert_id = request.data.get('alert_id')
        if not alert_id:
            return Response({'error': 'alert_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        alert = Alert.objects.filter(id=alert_id, student=request.user).first()
        if not alert:
            return Response({'error': 'Notification not found'}, status=status.HTTP_404_NOT_FOUND)

        if alert.status == Alert.Status.ACTIVE:
            alert.status = Alert.Status.ACKNOWLEDGED
            alert.acknowledged_at = timezone.now()
            alert.save(update_fields=['status', 'acknowledged_at'])

        unread_count = _deduped_unread_count(request.user)
        return Response({
            'message': 'Notification marked as read',
            'status': alert.status,
            'unread_count': unread_count,
        })
    

class RiskDataAPI(APIView):
    """
    API for risk-related data visualizations
    """
    # Make authentication optional - let the permission class handle it
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    
    def get(self, request, format=None):
        # The user should be authenticated via the permission class
        teacher = request.user
        
        # Get parameters
        course_id = request.query_params.get('course_id')
        try:
            days = int(request.query_params.get('days', 30))
        except (TypeError, ValueError):
            days = 30
        days = max(1, min(days, 365))
        
        # Base queryset
        enrollments = Enrollment.objects.filter(
            course__teacher=teacher,
            status='ACTIVE'
        )
        
        if course_id:
            enrollments = enrollments.filter(course_id=course_id)
        
        # Risk distribution pie chart
        risk_counts = enrollments.values('risk_level').annotate(
            count=Count('id')
        ).order_by('risk_level')
        
        risk_distribution = {
            'labels': [],
            'data': [],
            'colors': [],
        }
        
        color_map = {
            'LOW': '#10b981',
            'MEDIUM': '#f59e0b',
            'HIGH': '#ef4444',
            'CRITICAL': '#7f1d1d',
            'UNKNOWN': '#6b7280',
        }
        
        label_map = {
            'LOW': 'Low Risk',
            'MEDIUM': 'Medium Risk',
            'HIGH': 'High Risk',
            'CRITICAL': 'Critical',
            'UNKNOWN': 'Unknown',
        }
        
        for item in risk_counts:
            level = item['risk_level']
            risk_distribution['labels'].append(label_map.get(level, level))
            risk_distribution['data'].append(item['count'])
            risk_distribution['colors'].append(color_map.get(level, '#6b7280'))
        
        # Risk trend over time
        cutoff = timezone.now() - timedelta(days=days)
        risk_history = RiskHistory.objects.filter(
            course__teacher=teacher,
            calculated_at__gte=cutoff
        )
        if course_id:
            risk_history = risk_history.filter(course_id=course_id)

        trend_points = risk_history.values('calculated_at__date').annotate(
            avg_risk=Avg('risk_score'),
            max_risk=Max('risk_score'),
        ).order_by('calculated_at__date')

        risk_trend = {
            'dates': [h['calculated_at__date'].isoformat() for h in trend_points if h['calculated_at__date']],
            'avg_risk': [float(h['avg_risk'] or 0) for h in trend_points if h['calculated_at__date']],
            'max_risk': [float(h['max_risk'] or 0) for h in trend_points if h['calculated_at__date']],
        }
        
        return Response({
            'risk_distribution': risk_distribution,
            'risk_trend': risk_trend,
            'risk_trend_meta': {
                'x_axis': 'Date',
                'y_axis': 'Risk score (0-1)',
                'window_days': days,
            },
            'total_students': enrollments.count(),
        })

class StudentRiskDetailAPI(APIView):
    """
    Detailed risk data for a specific student
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    
    def get(self, request, student_id, course_id, format=None):
        """Get detailed risk history for a student"""
        
        # Get risk history
        history = list(RiskHistory.objects.filter(
            student_id=student_id,
            course_id=course_id
        ).order_by('calculated_at'))

        deduped_history = []
        last_signature = None
        for h in history:
            signature = (h.risk_level, round(float(h.risk_score), 3))
            if signature == last_signature:
                continue
            last_signature = signature
            deduped_history.append(h)
        
        history_data = [
            {
                'date': h.calculated_at.date().isoformat(),
                'risk_score': float(h.risk_score),
                'risk_level': h.risk_level,
                'performance': float(h.performance_score),
                'progress': float(h.progress_score),
                'engagement': float(h.engagement_score),
                'factors': h.contributing_factors,
            }
            for h in deduped_history
        ]
        
        # Get enrollment details
        enrollment = Enrollment.objects.filter(
            student_id=student_id,
            course_id=course_id
        ).first()
        
        if not enrollment:
            return Response(
                {'error': 'Enrollment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        explainability = _build_risk_explainability(enrollment)
        
        # Get recent alerts
        alerts = Alert.objects.filter(
            student_id=student_id,
            course_id=course_id
        ).order_by('-generated_at')[:5]
        
        alerts_data = [
            {
                'id': str(a.id),
                'type': a.get_alert_type_display(),
                'severity': a.severity,
                'title': a.title,
                'generated_at': a.generated_at.isoformat(),
                'status': a.status,
            }
            for a in alerts
        ]
        
        return Response({
            'student_name': enrollment.student.display_name,
            'course_title': enrollment.course.title,
            'current_risk': {
                'score': float(enrollment.risk_score),
                'score_percent': round(float(enrollment.risk_score) * 100, 1),
                'level': enrollment.risk_level,
                'progress': float(enrollment.progress_percentage),
                'avg_quiz': float(enrollment.average_quiz_score),
                'last_active': enrollment.last_activity.isoformat(),
            },
            'explainability': explainability,
            'history': history_data[-30:],  # Last 30 entries
            'alerts': alerts_data,
        })


class AlertManagementAPI(APIView):
    """
    API for managing alerts
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    
    def get(self, request, format=None):
        """Get alerts with filtering"""
        teacher = request.user
        AlertGenerator._resolve_old_alerts()
        
        # Filter parameters
        status_filter = request.query_params.get('status', 'ACTIVE,ACKNOWLEDGED')
        severity = request.query_params.get('severity')
        alert_type = request.query_params.get('type')
        course_id = request.query_params.get('course_id')
        
        alerts = Alert.objects.filter(
            teacher=teacher,
            alert_type__in=RISK_ALERT_TYPES
        )
        
        if status_filter:
            status_list = status_filter.split(',')
            alerts = alerts.filter(status__in=status_list)
        
        if severity:
            alerts = alerts.filter(severity=severity)
        
        if alert_type:
            alerts = alerts.filter(alert_type=alert_type)
        
        if course_id:
            alerts = alerts.filter(course_id=course_id)
        
        severity_counts = {
            'CRITICAL': 0,
            'HIGH': 0,
            'MEDIUM': 0,
            'LOW': 0,
            'INFO': 0,
        }
        for item in alerts.values('severity').annotate(count=Count('id')):
            severity = item.get('severity')
            if severity in severity_counts:
                severity_counts[severity] = item['count']

        status_counts = {
            'ACTIVE': 0,
            'ACKNOWLEDGED': 0,
            'RESOLVED': 0,
            'DISMISSED': 0,
            'EXPIRED': 0,
        }
        for item in alerts.values('status').annotate(count=Count('id')):
            current_status = item.get('status')
            if current_status in status_counts:
                status_counts[current_status] = item['count']

        alerts = alerts.annotate(
            status_rank=Case(
                When(status=Alert.Status.ACTIVE, then=Value(0)),
                When(status=Alert.Status.ACKNOWLEDGED, then=Value(1)),
                When(status=Alert.Status.RESOLVED, then=Value(2)),
                When(status=Alert.Status.DISMISSED, then=Value(3)),
                When(status=Alert.Status.EXPIRED, then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            ),
            severity_rank=Case(
                When(severity=Alert.Severity.CRITICAL, then=Value(0)),
                When(severity=Alert.Severity.HIGH, then=Value(1)),
                When(severity=Alert.Severity.MEDIUM, then=Value(2)),
                When(severity=Alert.Severity.LOW, then=Value(3)),
                When(severity=Alert.Severity.INFO, then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            ),
        ).select_related('student', 'course').order_by('status_rank', 'severity_rank', '-generated_at')
        
        # Pagination
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        total = alerts.count()
        page_alerts = alerts[offset:offset + limit]
        
        alerts_data = []
        for alert in page_alerts:
            alerts_data.append({
                'id': str(alert.id),
                'student_id': str(alert.student.id),
                'student_name': alert.student.display_name,
                'course_id': str(alert.course.id) if alert.course else None,
                'course_title': alert.course.title if alert.course else 'N/A',
                'alert_type': alert.get_alert_type_display(),
                'alert_type_code': alert.alert_type,
                'severity': alert.severity,
                'status': alert.status,
                'title': alert.title,
                'message': alert.message,
                'recommendation': alert.recommendation,
                'risk_score': float(alert.risk_score) if alert.risk_score is not None else None,
                'engagement_score': float(alert.engagement_score) if alert.engagement_score is not None else None,
                'progress_percentage': float(alert.progress_percentage) if alert.progress_percentage is not None else None,
                'generated_at': alert.generated_at.isoformat(),
                'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            })
        
        return Response({
            'total': total,
            'limit': limit,
            'offset': offset,
            'alerts': alerts_data,
            'summary': {
                'severity_counts': severity_counts,
                'status_counts': status_counts,
                'unresolved': status_counts['ACTIVE'] + status_counts['ACKNOWLEDGED'],
                'resolved': status_counts['RESOLVED'],
            }
        })
    
    def post(self, request, format=None):
        """Update alert status"""
        alert_id = request.data.get('alert_id')
        action = request.data.get('action')  # acknowledge, resolve, dismiss
        
        try:
            alert = Alert.objects.get(
                id=alert_id,
                teacher=request.user
            )
            
            if action == 'acknowledge':
                alert.acknowledge()
                message = 'Alert acknowledged'
            elif action == 'resolve':
                outcome = request.data.get('outcome', '')
                alert.resolve(outcome)
                message = 'Alert resolved'
            elif action == 'dismiss':
                alert.status = Alert.Status.DISMISSED
                alert.save()
                message = 'Alert dismissed'
            else:
                return Response(
                    {'error': 'Invalid action'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({
                'message': message,
                'alert_id': alert_id,
                'status': alert.status,
            })
            
        except Alert.DoesNotExist:
            return Response(
                {'error': 'Alert not found'},
                status=status.HTTP_404_NOT_FOUND
            )


from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin


class DifficultyAnalysisView(LoginRequiredMixin, TemplateView):
    """
    Template view for detailed lesson difficulty analysis
    Shows all lessons ranked by difficulty with failure rates, access patterns, etc.
    """
    template_name = 'dashboard/teacher/difficulty_analysis.html'
    login_url = 'login'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Topic Difficulty Analysis'
        context['courses'] = Course.objects.filter(
            teacher=self.request.user,
            status=Course.Status.PUBLISHED
        )
        return context


class DifficultyAPI(APIView):
    """
    API for difficulty analytics
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    
    def get(self, request, format=None):
        """Get difficulty data for charts"""
        teacher = request.user
        course_id = request.query_params.get('course_id')

        # Keep difficulty snapshots fresh so all pages show consistent values.
        if course_id:
            DifficultyAnalyzer.analyze_course_difficulties(str(course_id))
        else:
            teacher_course_ids = Course.objects.filter(
                teacher=teacher,
                status=Course.Status.PUBLISHED
            ).values_list('id', flat=True)
            for cid in teacher_course_ids:
                DifficultyAnalyzer.analyze_course_difficulties(str(cid))
        
        difficulties = LessonDifficulty.objects.filter(
            lesson__module__course__teacher=teacher
        ).select_related('lesson__module__course')
        
        if course_id:
            difficulties = difficulties.filter(lesson__module__course_id=course_id)
        
        # Difficulty distribution
        distribution = difficulties.values('difficulty_level').annotate(
            count=Count('id')
        ).order_by('difficulty_level')
        
        # Top hardest lessons
        hardest = difficulties.order_by('-difficulty_score')[:10]
        
        hardest_data = []
        for d in hardest:
            active_students_in_course = Enrollment.objects.filter(
                course=d.lesson.module.course,
                status=Enrollment.Status.ACTIVE
            ).values('student_id').distinct().count()
            access_coverage_pct = (
                (float(d.unique_students or 0) / float(active_students_in_course)) * 100.0
                if active_students_in_course > 0 else 0.0
            )
            hardest_data.append({
                'lesson_id': str(d.lesson.id),
                'lesson_title': d.lesson.title,
                'course_title': d.lesson.module.course.title,
                'difficulty_score': float(d.difficulty_score),
                'difficulty_level': d.difficulty_level,
                'difficulty_label': difficulty_display_label(d.difficulty_level),
                'failure_rate': float(d.failure_rate),
                'attempt_intensity': float(d.attempt_intensity),
                'access_count': int(d.total_views or 0),
                'access_coverage_pct': round(access_coverage_pct, 1),
                'access_frequency': float(d.access_frequency),
            })
        
        return Response({
            'distribution': [
                {
                    'level': item['difficulty_level'],
                    'label': difficulty_display_label(item['difficulty_level']),
                    'count': item['count'],
                }
                for item in distribution
            ],
            'hardest_lessons': hardest_data,
            'total_analyzed': difficulties.count(),
        })

class TeacherDashboardCachedAPI(APIView):
    """
    Teacher dashboard API with Redis caching
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    
    def get(self, request, format=None):
        teacher = request.user
        teacher_id = str(teacher.id)  # type: ignore
        
        # Try to get from cache
        cached_data = DashboardCache.get_teacher_dashboard(teacher_id)
        if cached_data:
            return Response(cached_data)
        
        # Calculate fresh data
        data = self._calculate_dashboard_data(teacher)
        
        # Store in cache
        DashboardCache.set_teacher_dashboard(teacher_id, data)
        
        return Response(data)
    
    def _calculate_dashboard_data(self, teacher):
        """Calculate all dashboard data"""
        # Get teacher's courses
        courses = Course.objects.filter(teacher=teacher, status='PUBLISHED')
        course_ids = courses.values_list('id', flat=True)
        
        # Get active enrollments
        enrollments = Enrollment.objects.filter(
            course_id__in=course_ids,
            status='ACTIVE'
        ).select_related('student', 'course')
        
        # Calculate KPIs
        total_students = enrollments.count()
        high_risk_count = enrollments.filter(risk_level__in=['HIGH', 'CRITICAL']).count()
        medium_risk_count = enrollments.filter(risk_level='MEDIUM').count()
        low_risk_count = enrollments.filter(risk_level='LOW').count()
        
        # Average performance
        avg_performance = enrollments.aggregate(
            avg=Avg('average_quiz_score')
        )['avg'] or 0
        
        # Recent alerts
        recent_alerts = Alert.objects.filter(
            teacher=teacher,
            status__in=['ACTIVE', 'ACKNOWLEDGED'],
            alert_type__in=RISK_ALERT_TYPES
        ).select_related('student', 'course').order_by('-generated_at')[:10]
        
        # Risk distribution by course
        course_risk = []
        for course in courses[:5]:
            course_enrollments = enrollments.filter(course=course)
            if course_enrollments.exists():
                course_risk.append({
                    'course_id': str(course.id),
                    'course_title': course.title,
                    'total': course_enrollments.count(),
                    'high_risk': course_enrollments.filter(
                        risk_level__in=['HIGH', 'CRITICAL']
                    ).count(),
                    'medium_risk': course_enrollments.filter(risk_level='MEDIUM').count(),
                    'low_risk': course_enrollments.filter(risk_level='LOW').count(),
                })
        
        # Hardest topics
        hardest_topics = LessonDifficulty.objects.filter(
            lesson__module__course__teacher=teacher
        ).select_related('lesson__module__course').order_by('-difficulty_score')[:10]
        
        # Format data
        return {
            'kpi': {
                'total_students': total_students,
                'high_risk_count': high_risk_count,
                'medium_risk_count': medium_risk_count,
                'low_risk_count': low_risk_count,
                'avg_performance': round(avg_performance, 1),
                'active_alerts': recent_alerts.count(),
            },
            'risk_distribution': {
                'labels': ['Low Risk', 'Medium Risk', 'High Risk', 'Critical'],
                'data': [low_risk_count, medium_risk_count, high_risk_count,
                        enrollments.filter(risk_level='CRITICAL').count()],
                'colors': ['#10b981', '#f59e0b', '#ef4444', '#7f1d1d'],
            },
            'course_risk': course_risk,
            'recent_alerts': [
                {
                    'id': str(a.id),
                    'student_name': a.student.display_name,  # type: ignore
                    'course_title': a.course.title if a.course else 'N/A',
                    'alert_type': a.get_alert_type_display(),  # type: ignore
                    'severity': a.severity,
                    'title': a.title,
                    'message': a.message,
                    'generated_at': a.generated_at.isoformat(),
                    'status': a.status,
                }
                for a in recent_alerts
            ],
            'hardest_topics': [
                {
                    'lesson_id': str(t.lesson.id),
                    'lesson_title': t.lesson.title,
                    'course_title': t.lesson.module.course.title,
                    'difficulty_score': float(t.difficulty_score),
                    'difficulty_level': t.difficulty_level,
                    'difficulty_label': difficulty_display_label(t.difficulty_level),
                    'failure_rate': float(t.failure_rate),
                }
                for t in hardest_topics
            ],
        }
    
    def post(self, request, format=None):
        """Invalidate cache"""
        teacher_id = str(request.user.id)  # type: ignore
        DashboardCache.invalidate_teacher_dashboard(teacher_id)
        RiskCache.invalidate_risk_distribution(teacher_id)
        return Response({'message': 'Cache cleared'})



class DifficultyCachedAPI(APIView):
    """
    Difficulty data API with caching
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    
    def get(self, request, format=None):
        teacher = request.user
        teacher_id = str(teacher.id)  # type: ignore
        limit = int(request.query_params.get('limit', 10))
        
        # Try to get from cache
        cached_data = DifficultyCache.get_hardest_lessons(teacher_id, limit)
        if cached_data:
            return Response({'hardest_lessons': cached_data})
        
        # Calculate fresh data
        difficulties = LessonDifficulty.objects.filter(
            lesson__module__course__teacher=teacher
        ).select_related('lesson__module__course').order_by('-difficulty_score')[:limit]
        
        data = [
            {
                'lesson_id': str(d.lesson.id),
                'lesson_title': d.lesson.title,
                'course_title': d.lesson.module.course.title,
                'difficulty_score': float(d.difficulty_score),
                'difficulty_level': d.difficulty_level,
                'difficulty_label': difficulty_display_label(d.difficulty_level),
                'failure_rate': float(d.failure_rate),
            }
            for d in difficulties
        ]
        
        # Store in cache
        DifficultyCache.set_hardest_lessons(teacher_id, data, limit)
        
        return Response({'hardest_lessons': data})
    
    def post(self, request, format=None):
        """Invalidate difficulty cache"""
        DifficultyCache.invalidate_difficulty_cache()
        return Response({'message': 'Difficulty cache cleared'})

