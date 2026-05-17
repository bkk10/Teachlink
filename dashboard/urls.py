from django.urls import path
from . import views

urlpatterns = [
    # Template views
    path('difficulty-analysis/', views.DifficultyAnalysisView.as_view(), name='difficulty_analysis'),
    path('help/', views.HelpSupportView.as_view(), name='dashboard_help'),
    path('pending-assessments/', views.PendingAssessmentsView.as_view(), name='student_pending_assessments'),
    path('risk-history/', views.RiskHistoryView.as_view(), name='student_risk_history'),
    path('deadlines/', views.DeadlinesView.as_view(), name='student_deadlines'),
    
    # API views - exposed under /api/dashboard/...
    path('teacher/', views.TeacherDashboardAPI.as_view(), name='teacher_api'),
    path('student/', views.StudentDashboardAPI.as_view(), name='student_api'),
    path('student/notifications/', views.StudentNotificationAPI.as_view(), name='student_notifications_api'),
    path('risk-data/', views.RiskDataAPI.as_view(), name='risk_data_api'),
    path('risk/<uuid:student_id>/<uuid:course_id>/', views.StudentRiskDetailAPI.as_view(), name='student_risk_api'),
    path('alerts/', views.AlertManagementAPI.as_view(), name='alerts_api'),
    path('difficulty/', views.DifficultyAPI.as_view(), name='difficulty_api'),
    path('lesson-students/', views.LessonStudentsAPI.as_view(), name='lesson_students_api'),
    path('attendance/<uuid:course_id>/', views.AttendanceAPI.as_view(), name='attendance_api'),
    path('attendance/', views.AttendanceAPI.as_view(), name='attendance_api_base'),
    path('api/attendance/log/', views.api_attendance_log, name='api_attendance_log'),
]
