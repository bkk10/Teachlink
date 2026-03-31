"""
Course Management Serializers
"""
from rest_framework import serializers
from django.utils import timezone
from .models import Course, Module, Lesson, LessonCompletion, Enrollment, Competency, LessonCompetency, AttendanceRecord
from users.serializers import UserSerializer

class LessonSerializer(serializers.ModelSerializer):
    """Lesson serializer"""
    display_duration = serializers.SerializerMethodField()
    
    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'content_type', 'content_text', 'content_html',
            'video_url', 'resource_file', 'external_url',
            'order', 'is_published', 'estimated_minutes', 'display_duration',
            'word_count_estimated', 'icon_color',
            'difficulty_level', 'difficulty_score',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'difficulty_level', 'difficulty_score',
                          'word_count_estimated', 'icon_color',
                          'display_duration', 'created_at', 'updated_at']
    
    def get_display_duration(self, obj):
        """Return the display duration (estimated or calculated from content)"""
        return obj.get_display_duration()


class LessonDetailSerializer(serializers.ModelSerializer):
    """Detailed lesson serializer with completion status"""
    is_completed = serializers.SerializerMethodField()
    
    class Meta:
        model = Lesson
        fields = LessonSerializer.Meta.fields + ['is_completed']
    def get_is_completed(self, obj):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated and hasattr(request.user, 'role') and request.user.role == 'STUDENT':
            return LessonCompletion.objects.filter(
                student=request.user,
                lesson=obj
            ).exists()
        return False
class ModuleSerializer(serializers.ModelSerializer):
    """Module serializer with lessons"""
    lessons = LessonSerializer(many=True, read_only=True)
    total_lessons = serializers.IntegerField(read_only=True)  # ✅ REMOVED redundant source
    
    class Meta:
        model = Module
        fields = [
            'id', 'title', 'description', 'order',
            'estimated_minutes', 'lessons', 'total_lessons',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    

class ModuleDetailSerializer(serializers.ModelSerializer):
    """Detailed module serializer with full lesson details"""
    lessons = LessonDetailSerializer(many=True, read_only=True)
    
    class Meta:
        model = Module
        fields = ModuleSerializer.Meta.fields


class CourseSerializer(serializers.ModelSerializer):
    """Course list/overview serializer"""
    teacher_name = serializers.CharField(source='teacher.display_name', read_only=True)
    total_students = serializers.IntegerField(read_only=True)
    total_modules = serializers.IntegerField(read_only=True)
    total_lessons = serializers.IntegerField(read_only=True)
    high_risk_count = serializers.IntegerField(read_only=True)
    medium_risk_count = serializers.IntegerField(read_only=True)
    low_risk_count = serializers.IntegerField(read_only=True)
    avg_progress = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    avg_quiz_score = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    health_status_summary = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'teacher', 'teacher_name',
            'status', 'enrollment_key', 'thumbnail', 'start_date', 'end_date',
            'expected_hours', 'total_students', 'total_modules', 'total_lessons',
            'high_risk_count', 'medium_risk_count', 'low_risk_count',
            'avg_progress', 'avg_quiz_score', 'health_status_summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'teacher', 'created_at', 'updated_at']
    
    def get_health_status_summary(self, obj):
        """Return course health status"""
        return obj.health_status_summary
class CourseDetailSerializer(serializers.ModelSerializer):
    """Detailed course serializer with related data"""
    teacher_name = serializers.CharField(source='teacher.display_name', read_only=True)
    total_students = serializers.IntegerField(read_only=True)
    total_modules = serializers.IntegerField(read_only=True)
    total_lessons = serializers.IntegerField(read_only=True)
    modules = ModuleSerializer(many=True, read_only=True)
    enrollment_status = serializers.SerializerMethodField()
    student_progress = serializers.SerializerMethodField()
    health_status_summary = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'teacher', 'teacher_name',
            'status', 'enrollment_key', 'start_date', 'end_date', 'expected_hours',
            'thumbnail', 'created_at', 'updated_at',
            'total_students', 'total_modules', 'total_lessons', 'modules',
            'enrollment_status', 'student_progress', 'health_status_summary'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_health_status_summary(self, obj):
        """Return course health status"""
        return obj.health_status_summary
    
    def get_enrollment_status(self, obj):
        """Get current user's enrollment status"""
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated and hasattr(request.user, 'role') and request.user.role == 'STUDENT':
            try:
                enrollment = Enrollment.objects.get(
                    student=request.user,
                    course=obj
                )
                return {
                    'is_enrolled': True,
                    'status': enrollment.status,
                    'progress': enrollment.progress_percentage,
                    'enrolled_at': enrollment.enrolled_at
                }
            except Enrollment.DoesNotExist:
                pass
        return {'is_enrolled': False}
    
    def get_student_progress(self, obj):  # 👈 THIS METHOD MUST BE INDENTED INSIDE THE CLASS
        """Get detailed progress for current student"""
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated and hasattr(request.user, 'role') and request.user.role == 'STUDENT':
            try:
                enrollment = Enrollment.objects.get(
                    student=request.user,
                    course=obj
                )
                return {
                    'progress': enrollment.progress_percentage,
                    'risk_level': enrollment.risk_level,
                    'engagement_score': enrollment.engagement_score,
                    'last_activity': enrollment.last_activity,
                    'completed_lessons': LessonCompletion.objects.filter(
                        student=request.user,
                        lesson__module__course=obj
                    ).count()
                }
            except Enrollment.DoesNotExist:
                pass
        return None

class EnrollmentSerializer(serializers.ModelSerializer):
    """Enrollment serializer"""
    student_name = serializers.CharField(source='student.display_name', read_only=True)
    student_email = serializers.EmailField(source='student.email', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    previous_risk_score = serializers.SerializerMethodField()
    risk_trend = serializers.SerializerMethodField()
    
    class Meta:
        model = Enrollment
        fields = [
            'id', 'student', 'student_name', 'student_email',
            'course', 'course_title', 'enrolled_at', 'status',
            'progress_percentage', 'average_quiz_score',
            'last_activity', 'risk_score', 'previous_risk_score', 'risk_level', 'risk_trend',
            'engagement_score', 'completed_at'
        ]
        read_only_fields = [
            'id', 'enrolled_at', 'progress_percentage',
            'risk_score', 'risk_level', 'engagement_score'
        ]

    def _latest_two_scores(self, obj):
        latest = list(
            obj.risk_history.order_by('-calculated_at').values_list('risk_score', flat=True)[:2]
        )
        current = float(obj.risk_score or 0)
        previous = float(latest[1]) if len(latest) > 1 else float(latest[0]) if latest else current
        return current, previous

    def get_previous_risk_score(self, obj):
        _, previous = self._latest_two_scores(obj)
        return previous

    def get_risk_trend(self, obj):
        current, previous = self._latest_two_scores(obj)
        delta = current - previous
        if abs(delta) <= 0.05:
            return 'STABLE'
        if delta < 0:
            return 'IMPROVING'
        return 'DECLINING'


class EnrollmentDetailSerializer(serializers.ModelSerializer):
    """Detailed enrollment serializer for analytics"""
    student = UserSerializer(read_only=True)
    course = CourseSerializer(read_only=True)
    days_inactive = serializers.IntegerField(source='days_since_last_activity', read_only=True)
    
    class Meta:
        model = Enrollment
        fields = EnrollmentSerializer.Meta.fields + ['days_inactive']


class LessonCompletionSerializer(serializers.ModelSerializer):
    """Lesson completion serializer"""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    
    class Meta:
        model = LessonCompletion
        fields = [
            'id', 'student', 'lesson', 'lesson_title',
            'completed_at', 'time_spent_seconds'
        ]
        read_only_fields = ['id', 'completed_at']


class CompetencySerializer(serializers.ModelSerializer):
    """Competency serializer"""
    
    class Meta:
        model = Competency
        fields = [
            'id', 'course', 'name', 'description', 'category',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LessonCompetencySerializer(serializers.ModelSerializer):
    """Lesson competency mapping serializer"""
    competency_name = serializers.CharField(source='competency.name', read_only=True)
    
    class Meta:
        model = LessonCompetency
        fields = ['id', 'lesson', 'competency', 'competency_name', 'weight']
        read_only_fields = ['id']


class AttendanceRecordSerializer(serializers.ModelSerializer):
    """Attendance record serializer (Phase 4)"""
    student_name = serializers.CharField(source='student.display_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'student', 'student_name', 'course', 'course_title',
            'session_date', 'status', 'notes',
            'recorded_at', 'updated_at'
        ]
        read_only_fields = ['id', 'recorded_at', 'updated_at']
