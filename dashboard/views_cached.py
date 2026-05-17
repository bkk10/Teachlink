"""
Dashboard Views with Redis Caching
"""
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Count, Avg
from datetime import timedelta
from typing import Optional

from analytics.services.cache_services import DashboardCache, RiskCache, DifficultyCache
from analytics.models import Alert, LessonDifficulty
from courses.models import Course, Enrollment
from users.permissions import IsTeacher, IsStudent


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


class TeacherDashboardCachedAPI(APIView):
    """
    Teacher dashboard API with Redis caching
    """
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
            status__in=['ACTIVE', 'ACKNOWLEDGED']
        ).select_related('student', 'course').order_by('-generated_at')[:10]
        
        # Count unique students with active alerts (not alert count)
        students_with_alerts = Alert.objects.filter(
            teacher=teacher,
            status__in=['ACTIVE', 'ACKNOWLEDGED']
        ).values('student').distinct().count()
        
        # Count unique students requiring attention (HIGH/CRITICAL risk)
        students_requiring_attention = enrollments.filter(
            risk_level__in=['HIGH', 'CRITICAL']
        ).values('student').distinct().count()
        
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
                'total_unique_students': enrollments.values('student').distinct().count(),
                'high_risk_count': high_risk_count,
                'medium_risk_count': medium_risk_count,
                'low_risk_count': low_risk_count,
                'avg_performance': round(avg_performance, 1),
                'active_alerts': recent_alerts.count(),
                'students_with_alerts': students_with_alerts,
            },
            'risk_engine_summary': {
                'formula': '40% Progress + 40% Quiz + 20% Inactivity',
                'students_requiring_attention': students_requiring_attention,
                'highest_risk_score_pct': round(
                    float(enrollments.order_by('-risk_score').first().risk_score * 100) if enrollments.exists() else 0, 1
                ),
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


class RiskDataCachedAPI(APIView):
    """
    Risk data API with caching
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    
    def get(self, request, format=None):
        teacher = request.user
        teacher_id = str(teacher.id)  # type: ignore
        course_id = request.query_params.get('course_id')
        
        # Try to get from cache
        cached_data = RiskCache.get_risk_distribution(teacher_id, course_id)
        if cached_data:
            return Response(cached_data)
        
        # Calculate fresh data
        data = self._calculate_risk_data(teacher, course_id)
        
        # Store in cache
        RiskCache.set_risk_distribution(teacher_id, data, course_id)
        
        return Response(data)
    
    def _calculate_risk_data(self, teacher, course_id: Optional[str] = None):
        """Calculate risk distribution data"""
        # Base queryset
        enrollments = Enrollment.objects.filter(
            course__teacher=teacher,
            status='ACTIVE'
        )
        
        if course_id:
            enrollments = enrollments.filter(course_id=course_id)
        
        # Risk distribution
        risk_counts = enrollments.values('risk_level').annotate(
            count=Count('id')
        ).order_by('risk_level')
        
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
        
        distribution = {
            'labels': [],
            'data': [],
            'colors': [],
        }
        
        for item in risk_counts:
            level = item['risk_level']
            distribution['labels'].append(label_map.get(level, level))
            distribution['data'].append(item['count'])
            distribution['colors'].append(color_map.get(level, '#6b7280'))
        
        return {
            'risk_distribution': distribution,
            'total_students': enrollments.count(),
        }
    
    def post(self, request, format=None):
        """Invalidate risk cache"""
        teacher_id = str(request.user.id)  # type: ignore
        RiskCache.invalidate_risk_distribution(teacher_id)
        return Response({'message': 'Risk cache cleared'})


class DifficultyCachedAPI(APIView):
    """
    Difficulty data API with caching
    """
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
