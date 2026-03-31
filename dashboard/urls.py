from django.urls import path
from . import views

urlpatterns = [
    # Template views
    path('difficulty-analysis/', views.DifficultyAnalysisView.as_view(), name='difficulty_analysis'),
    
    # API views - exposed under /api/dashboard/...
    path('teacher/', views.TeacherDashboardAPI.as_view(), name='teacher_api'),
    path('student/', views.StudentDashboardAPI.as_view(), name='student_api'),
    path('student/notifications/', views.StudentNotificationAPI.as_view(), name='student_notifications_api'),
    path('risk-data/', views.RiskDataAPI.as_view(), name='risk_data_api'),
    path('risk/<uuid:student_id>/<uuid:course_id>/', views.StudentRiskDetailAPI.as_view(), name='student_risk_api'),
    path('alerts/', views.AlertManagementAPI.as_view(), name='alerts_api'),
    path('difficulty/', views.DifficultyAPI.as_view(), name='difficulty_api'),
]
