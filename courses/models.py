"""
Course Management Models for TeachLink
- Course, Module, Lesson hierarchy
- Enrollment tracking
- Progress monitoring
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid


def default_course_key():
    """Generate a short enrollment key for students."""
    return uuid.uuid4().hex[:8].upper()


class Course(models.Model):
    """
    Main course container created by teachers
    """
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PUBLISHED = 'PUBLISHED', 'Published'
        ARCHIVED = 'ARCHIVED', 'Archived'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Core fields
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='courses_teaching',
        limit_choices_to={'role': 'TEACHER'}
    )
    
    # Course settings
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.DRAFT
    )
    enrollment_key = models.CharField(
        max_length=12,
        unique=True,
        default=default_course_key,
        help_text="Key students can use to self-enroll"
    )
    
    # Timeline
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    expected_hours = models.PositiveIntegerField(
        default=0,
        help_text="Expected total hours to complete"
    )
    
    # Media
    thumbnail = models.ImageField(
        upload_to='course_thumbnails/', 
        blank=True, 
        null=True
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'courses'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['teacher', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def total_students(self):
        """Get total enrolled students"""
        return self.enrollments.filter(
            status=Enrollment.Status.ACTIVE
        ).count()
    
    @property
    def total_modules(self):
        """Get total modules in course"""
        return self.modules.count()
    
    @property
    def total_lessons(self):
        """Get total lessons across all modules"""
        from .models import Lesson
        return Lesson.objects.filter(
            module__course=self
        ).count()
    
    @property
    def health_status_summary(self):
        """
        Get course health summary based on student risk levels.
        Returns: dict with counts by risk level and color
        Example: {'high_risk': 2, 'medium_risk': 3, 'low_risk': 5, 'status_color': 'RED'}
        """
        enrollments = self.enrollments.filter(status=Enrollment.Status.ACTIVE)
        high_risk_count = enrollments.filter(risk_level='HIGH').count()
        medium_risk_count = enrollments.filter(risk_level='MEDIUM').count()
        low_risk_count = enrollments.filter(risk_level='LOW').count()
        
        # Determine status color
        status_color = 'GREEN'
        if high_risk_count > 0:
            status_color = 'RED'
        elif medium_risk_count > 0:
            status_color = 'YELLOW'
        
        return {
            'high_risk': high_risk_count,
            'medium_risk': medium_risk_count,
            'low_risk': low_risk_count,
            'status_color': status_color,
            'total_at_risk': high_risk_count + medium_risk_count
        }

    def publish(self):
        """Publish the course"""
        self.status = self.Status.PUBLISHED
        self.save(update_fields=['status'])


class Module(models.Model):
    """
    Course module/unit container
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE, 
        related_name='modules'
    )
    
    # Core fields
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Ordering
    order = models.PositiveIntegerField(default=0)
    
    # Time estimate
    estimated_minutes = models.PositiveIntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'modules'
        ordering = ['order', 'created_at']
        unique_together = ['course', 'order']
        indexes = [
            models.Index(fields=['course', 'order']),
        ]
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"
    
    @property
    def total_lessons(self):
        """Get total lessons in module"""
        return self.lessons.count()
    
    def completed_lessons_count(self, student_id):
        """Get completed lessons count for a student"""
        return self.lessons.filter(
            completions__student_id=student_id,
            completions__completed_at__isnull=False
        ).count()


class Lesson(models.Model):
    """
    Individual lesson/content unit
    """
    class ContentType(models.TextChoices):
        VIDEO = 'VIDEO', 'Video'
        TEXT = 'TEXT', 'Text Article'
        QUIZ = 'QUIZ', 'Quiz Assessment'
        RESOURCE = 'RESOURCE', 'Resource Material'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    module = models.ForeignKey(
        Module, 
        on_delete=models.CASCADE, 
        related_name='lessons'
    )
    
    # Core fields
    title = models.CharField(max_length=200)
    content_type = models.CharField(
        max_length=20, 
        choices=ContentType.choices,
        default=ContentType.TEXT
    )
    
    # Content storage
    content_text = models.TextField(
        blank=True,
        help_text="Text content for TEXT type lessons"
    )
    content_html = models.TextField(
        blank=True,
        help_text="Rich HTML content for native text editor (replaces content_text)"
    )
    video_url = models.URLField(
        blank=True,
        help_text="YouTube/Vimeo URL for VIDEO type lessons"
    )
    resource_file = models.FileField(
        upload_to='lesson_resources/',
        blank=True,
        null=True
    )
    external_url = models.URLField(
        blank=True,
        help_text="External resource URL"
    )
    
    # Content metadata
    word_count_estimated = models.PositiveIntegerField(
        default=0,
        help_text="Auto-calculated word count from content_html"
    )
    icon_color = models.CharField(
        max_length=20,
        default='',
        blank=True,
        help_text="Color for UI badge (auto-set based on content_type)"
    )
    
    # Ordering
    order = models.PositiveIntegerField(default=0)
    
    # Settings
    is_published = models.BooleanField(default=False)
    estimated_minutes = models.PositiveIntegerField(
        default=None,
        null=True,
        blank=True,
        help_text="Auto-estimated or manually set. If None, calculated from content."
    )
    
    # Difficulty tracking
    difficulty_score = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Calculated difficulty score 0-1"
    )
    difficulty_level = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low'),
            ('MEDIUM', 'Medium'),
            ('HIGH', 'High'),
            ('UNKNOWN', 'Unknown')
        ],
        default='UNKNOWN'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lessons'
        ordering = ['order', 'created_at']
        unique_together = ['module', 'order']
        indexes = [
            models.Index(fields=['module', 'order']),
            models.Index(fields=['content_type']),
            models.Index(fields=['difficulty_level']),
        ]
    
    def __str__(self):
        return f"{self.module.title} - {self.title}"
    
    def calculate_word_count(self):
        """
        Calculate word count from HTML content by stripping tags.
        Returns: integer word count
        """
        import re
        if not self.content_html:
            return 0
        # Strip HTML tags
        text = re.sub(r'<[^>]+>', '', self.content_html)
        # Count words
        words = text.split()
        return len(words)
    
    def estimate_duration_from_content(self):
        """
        Estimate duration in minutes from word count.
        Algorithm: word_count / 200 WPM (conservative estimate) + 20% buffer
        Returns: integer minutes (minimum 1)
        """
        word_count = self.calculate_word_count()
        if word_count == 0:
            return 0
        # 200 words per minute (conservative reading speed)
        base_minutes = word_count / 200.0
        # Add 20% buffer
        with_buffer = base_minutes * 1.2
        return max(1, int(round(with_buffer)))
    
    def get_display_duration(self):
        """
        Get the duration to display to users.
        If estimated_minutes is manually set, use it.
        Otherwise, estimate from content.
        Returns: integer minutes or None if no content
        """
        if self.estimated_minutes is not None:
            return self.estimated_minutes
        return self.estimate_duration_from_content() or None
    
    def set_icon_color_from_type(self):
        """
        Auto-set icon_color based on content_type.
        COLOR_SCHEME:
        - VIDEO: Blue (#2563EB)
        - TEXT: Green (#10B981)
        - QUIZ: Orange (#F59E0B)
        - RESOURCE: Purple (#8B5CF6)
        """
        color_map = {
            self.ContentType.VIDEO: '#2563EB',
            self.ContentType.TEXT: '#10B981',
            self.ContentType.QUIZ: '#F59E0B',
            self.ContentType.RESOURCE: '#8B5CF6',
        }
        self.icon_color = color_map.get(self.content_type, '#6B7280')
    
    @property
    def has_quiz(self):
        """Check if lesson has associated quiz"""
        return hasattr(self, 'quiz')
    
    @property
    def total_views(self):
        """Get total views count"""
        # Comment out until analytics app is created
        return 0
    
    def update_difficulty(self):
        """
        Update lesson difficulty using the DifficultyAnalyzer service.
        Uses failure rate thresholds:
            <30% failure -> LOW
            30-60% failure -> MEDIUM
            >60% failure -> HIGH
        """
        try:
            from analytics.services.difficulty_analyzer import DifficultyAnalyzer
            result = DifficultyAnalyzer.analyze_lesson_difficulty(str(self.id))
            if result:
                self.difficulty_score = Decimal(str(result.get('difficulty_score', 0.0)))
                self.difficulty_level = result.get('difficulty_level', 'UNKNOWN')
                self.save(update_fields=['difficulty_score', 'difficulty_level'])
            else:
                # fallback safe defaults
                self.difficulty_score = Decimal('0.00')
                self.difficulty_level = 'UNKNOWN'
                self.save(update_fields=['difficulty_score', 'difficulty_level'])
        except Exception:
            self.difficulty_score = Decimal('0.00')
            self.difficulty_level = 'UNKNOWN'
            self.save(update_fields=['difficulty_score', 'difficulty_level'])
    
    def save(self, *args, **kwargs):
        """Override save to calculate word count and set icon color."""
        # Auto-calculate word count from content_html
        if self.content_html:
            self.word_count_estimated = self.calculate_word_count()
        
        # Auto-set icon color based on content type
        if not self.icon_color:
            self.set_icon_color_from_type()
        
        super().save(*args, **kwargs)


class LessonCompletion(models.Model):
    """
    Track student lesson completion
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lesson_completions',
        limit_choices_to={'role': 'STUDENT'}
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='completions'
    )
    
    # Completion tracking
    completed_at = models.DateTimeField(default=timezone.now)
    time_spent_seconds = models.PositiveIntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'lesson_completions'
        unique_together = ['student', 'lesson']
        indexes = [
            models.Index(fields=['student', 'completed_at']),
            models.Index(fields=['lesson', 'completed_at']),
        ]
    
    def __str__(self):
        return f"{self.student.display_name} completed {self.lesson.title}"


class Enrollment(models.Model):
    """
    Student enrollment in a course
    Tracks progress, risk, and engagement
    """
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        COMPLETED = 'COMPLETED', 'Completed'
        DROPPED = 'DROPPED', 'Dropped'
        EXPIRED = 'EXPIRED', 'Expired'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
        limit_choices_to={'role': 'STUDENT'}
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    
    # Enrollment details
    enrolled_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    is_fee_paid = models.BooleanField(default=False)
    
    # Progress tracking
    progress_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Performance tracking
    average_quiz_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Engagement tracking
    last_activity = models.DateTimeField(default=timezone.now)
    total_time_spent_seconds = models.PositiveIntegerField(default=0)
    login_count = models.PositiveIntegerField(default=0)
    
    # Risk assessment
    risk_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="0.00 = Low Risk, 1.00 = High Risk"
    )
    risk_level = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low Risk'),
            ('MEDIUM', 'Medium Risk'),
            ('HIGH', 'High Risk'),
            ('UNKNOWN', 'Unknown')
        ],
        default='UNKNOWN'
    )
    engagement_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="0.00 = Disengaged, 1.00 = Highly Engaged"
    )
    
    # Completion
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'enrollments'
        unique_together = ['student', 'course']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['course', 'status']),
            models.Index(fields=['risk_level', 'status']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return f"{self.student.display_name} enrolled in {self.course.title}"
    
    def update_progress(self):
        """Calculate and update course progress percentage"""
        total_lessons = Lesson.objects.filter(
            module__course=self.course
        ).count()
        
        completed_lessons = LessonCompletion.objects.filter(
            student=self.student,
            lesson__module__course=self.course
        ).count()
        
        if total_lessons > 0:
            self.progress_percentage = (Decimal(completed_lessons) / Decimal(total_lessons)) * 100
        else:
            self.progress_percentage = Decimal('0.00')
        
        self.save(update_fields=['progress_percentage'])
        return self.progress_percentage
    
    def update_last_activity(self):
        """Update last activity timestamp"""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
    
    def mark_completed(self):
        """Mark enrollment as completed"""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.progress_percentage = Decimal('100.00')
        self.save(update_fields=['status', 'completed_at', 'progress_percentage'])
    
    @property
    def days_since_last_activity(self):
        """Get days since last activity"""
        delta = timezone.now() - self.last_activity
        return delta.days
    
    @property
    def is_at_risk(self):
        """Quick check if student is at risk"""
        return self.risk_level in ['HIGH', 'MEDIUM']
    
    @property
    def is_inactive(self):
        """Check if student is inactive (>7 days)"""
        return self.days_since_last_activity > 7


class Competency(models.Model):
    """
    Topic/Competency skills for lessons and assessments.
    Enables granular tracking of what students have mastered.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='competencies'
    )
    
    # Core fields
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g., 'Math', 'Reading', 'Problem Solving'"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'competencies'
        unique_together = ['course', 'name']
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['course', 'category']),
        ]
    
    def __str__(self):
        return f"{self.course.title} - {self.name}"


class LessonCompetency(models.Model):
    """
    Links lessons to competencies.
    A lesson can teach multiple competencies with varying weights.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='competency_mappings'
    )
    competency = models.ForeignKey(
        Competency,
        on_delete=models.CASCADE,
        related_name='lesson_mappings'
    )
    
    # Weight (0-1): how much this competency is covered in the lesson
    weight = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="0-1, importance of this competency in the lesson"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'lesson_competencies'
        unique_together = ['lesson', 'competency']
        indexes = [
            models.Index(fields=['lesson']),
            models.Index(fields=['competency']),
        ]
    
    def __str__(self):
        return f"{self.lesson.title} -> {self.competency.name}"


class AttendanceRecord(models.Model):
    """
    Track student attendance in physical tutoring sessions (Phase 4).
    """
    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'Present'
        ABSENT = 'ABSENT', 'Absent'
        LATE = 'LATE', 'Late'
        EXCUSED = 'EXCUSED', 'Excused'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        limit_choices_to={'role': 'STUDENT'}
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    
    # Attendance details
    session_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PRESENT
    )
    notes = models.TextField(blank=True)
    
    # Metadata
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'attendance_records'
        unique_together = ['student', 'course', 'session_date']
        indexes = [
            models.Index(fields=['student', 'course']),
            models.Index(fields=['session_date']),
        ]
        ordering = ['-session_date']
    
    def __str__(self):
        return f"{self.student.display_name} - {self.course.title} ({self.session_date}): {self.status}"
