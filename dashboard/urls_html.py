"""HTML dashboard URLs for TeachLink."""
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import debug_views

urlpatterns = [
    # Auth URLs
    path('login/', views.custom_login, name='custom_login'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            email_template_name='registration/password_reset_email.txt',
            html_email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html'
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html'
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),
    path('register/', views.custom_register, name='dashboard_register'),
    path('logout/', views.custom_logout, name='dashboard_logout'),

    # Dashboard pages
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/courses/<uuid:course_id>/analytics/', views.teacher_course_analytics, name='teacher_course_analytics'),
    path('teacher/quizzes/<uuid:quiz_id>/builder/', views.teacher_quiz_builder, name='teacher_quiz_builder'),
    path('teacher/students/', views.teacher_students, name='teacher_students'),
    path('teacher/payments/', views.teacher_payments, name='teacher_payments'),
    path('teacher/students/<uuid:student_id>/<uuid:course_id>/', views.risk_detail, name='teacher_student_detail'),
    path('student/enroll-key/', views.student_enroll_by_key, name='student_enroll_by_key'),
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('student/courses/<uuid:course_id>/quizzes/', views.student_course_quizzes, name='student_course_quizzes'),
    path('student/quizzes/<uuid:quiz_id>/attempts/', views.student_quiz_attempts, name='student_quiz_attempts'),
    path('student/attempts/<uuid:attempt_id>/review/', views.student_quiz_review, name='student_quiz_review'),
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('alerts/', views.alerts_center, name='alerts_center'),
    path('courses/', views.courses_overview, name='dashboard_courses'),
    path('lesson/<uuid:lesson_id>/open/', views.open_lesson_material, name='open_lesson_material'),
    path('profile/', views.profile_view, name='dashboard_profile'),
    path('settings/', views.profile_view, name='settings'),
    # Debug/test routes to preview new templates
    path('debug/templates/', debug_views.templates_index, name='debug_templates'),
    path('debug/lesson/', debug_views.debug_lesson, name='debug_lesson'),
]
