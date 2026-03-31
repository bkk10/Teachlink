"""
Course Management URLs
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'courses', views.CourseViewSet, basename='course')
router.register(r'modules', views.ModuleViewSet, basename='module')
router.register(r'lessons', views.LessonViewSet, basename='lesson')
router.register(r'enrollments', views.EnrollmentViewSet, basename='enrollment')
router.register(r'competencies', views.CompetencyViewSet, basename='competency')
router.register(r'lesson-competencies', views.LessonCompetencyViewSet, basename='lesson-competency')
router.register(r'attendance-records', views.AttendanceRecordViewSet, basename='attendance-record')
router.register(r'risk-prediction', views.RiskPredictionViewSet, basename='risk-prediction')

urlpatterns = [
    path('', include(router.urls)),
]