"""
Analytics and Risk Detection Models for TeachLink
- Risk score history tracking
- Engagement metrics
- Topic difficulty analysis
- Alert management
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from courses.models import Course, Enrollment, Lesson
import uuid
from decimal import Decimal

User = get_user_model()

class RiskHistory(models.Model):
    """
    Historical tracking of student risk scores
    Enables trend analysis and intervention effectiveness tracking
    """
    class RiskLevel(models.TextChoices):
        LOW = 'LOW', 'Low Risk'
        MEDIUM = 'MEDIUM', 'Medium Risk'
        HIGH = 'HIGH', 'High Risk'
        CRITICAL = 'CRITICAL', 'Critical Risk'
        UNKNOWN = 'UNKNOWN', 'Unknown'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='risk_history',
        limit_choices_to={'role': 'STUDENT'}
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='risk_history'
    )
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='risk_history',
        null=True,
        blank=True
    )
    
    # Risk score (0-1, where 1 = highest risk)
    risk_score = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="0.000 = No risk, 1.000 = Critical risk"
    )
    risk_level = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.UNKNOWN
    )
    
    # Component scores
    performance_score = models.DecimalField(
        max_digits=4, decimal_places=3, default=0,
        help_text="0-1, higher = better performance"
    )
    progress_score = models.DecimalField(
        max_digits=4, decimal_places=3, default=0,
        help_text="0-1, higher = better progress"
    )
    engagement_score = models.DecimalField(
        max_digits=4, decimal_places=3, default=0,
        help_text="0-1, higher = more engaged"
    )
    
    # Contributing factors (stored as JSON for detailed analysis)
    contributing_factors = models.JSONField(
        default=dict,
        help_text="Factors that influenced this risk score"
    )
    
    # Metadata
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'risk_history'
        ordering = ['-calculated_at']
        indexes = [
            models.Index(fields=['student', '-calculated_at']),
            models.Index(fields=['course', 'risk_level']),
            models.Index(fields=['enrollment', '-calculated_at']),
            models.Index(fields=['calculated_at']),
        ]
    
    def __str__(self):
        return f"{self.student.display_name} - {self.course.title}: {self.risk_level} ({self.risk_score})"


class EngagementMetrics(models.Model):
    """
    Detailed engagement tracking for students
    Updated daily via cron job or signals
    """
    class EngagementLevel(models.TextChoices):
        HIGHLY_ENGAGED = 'HIGH', 'Highly Engaged'
        MODERATELY_ENGAGED = 'MEDIUM', 'Moderately Engaged'
        DISENGAGED = 'LOW', 'Disengaged'
        INACTIVE = 'INACTIVE', 'Inactive'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='engagement_metrics'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='engagement_metrics'
    )
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='engagement_metrics'
    )
    
    # Date range
    date = models.DateField(default=timezone.now)
    week = models.PositiveIntegerField(default=0)  # Week number since enrollment
    
    # Activity metrics
    login_count = models.PositiveIntegerField(default=0)
    lessons_viewed = models.PositiveIntegerField(default=0)
    lessons_completed = models.PositiveIntegerField(default=0)
    quiz_attempts = models.PositiveIntegerField(default=0)
    total_time_seconds = models.PositiveIntegerField(default=0)
    
    # Derived scores
    activity_frequency = models.DecimalField(
        max_digits=4, decimal_places=3, default=0,
        help_text="0-1, normalized login frequency"
    )
    completion_rate = models.DecimalField(
        max_digits=4, decimal_places=3, default=0,
        help_text="0-1, lessons completed vs assigned"
    )
    quiz_participation = models.DecimalField(
        max_digits=4, decimal_places=3, default=0,
        help_text="0-1, quiz attempts vs available"
    )
    
    # Overall engagement
    engagement_score = models.DecimalField(
        max_digits=4, decimal_places=3, default=0,
        help_text="0-1 composite score"
    )
    engagement_level = models.CharField(
        max_length=20,
        choices=EngagementLevel.choices,
        default=EngagementLevel.DISENGAGED
    )
    
    # Trend
    trend_direction = models.CharField(
        max_length=10,
        choices=[
            ('IMPROVING', 'Improving'),
            ('DECLINING', 'Declining'),
            ('STABLE', 'Stable'),
            ('UNKNOWN', 'Unknown')
        ],
        default='UNKNOWN'
    )
    
    class Meta:
        db_table = 'engagement_metrics'
        unique_together = ['student', 'course', 'date']
        indexes = [
            models.Index(fields=['student', '-date']),
            models.Index(fields=['course', 'engagement_level']),
            models.Index(fields=['date']),
        ]
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.student.display_name} - {self.date}: {self.engagement_level}"


class LessonDifficulty(models.Model):
    """
    Track lesson difficulty based on student performance
    Updated after each quiz attempt
    """
    class DifficultyLevel(models.TextChoices):
        LOW = 'LOW', 'Low Difficulty'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High Difficulty'
        # Legacy values kept for compatibility with existing records.
        VERY_EASY = 'VERY_EASY', 'Very Easy'
        EASY = 'EASY', 'Easy'
        HARD = 'HARD', 'Hard'
        VERY_HARD = 'VERY_HARD', 'Very Hard'
        UNKNOWN = 'UNKNOWN', 'Unknown'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationship
    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name='difficulty_analysis'
    )
    
    # Core metrics
    failure_rate = models.DecimalField(
        max_digits=4, decimal_places=3, default=0,
        help_text="0-1, proportion of students who failed"
    )
    attempt_intensity = models.DecimalField(
        max_digits=4, decimal_places=3, default=0,
        help_text="0-1, normalized average attempts per student"
    )
    access_frequency = models.DecimalField(
        max_digits=4, decimal_places=3, default=0,
        help_text="0-1, normalized views vs expected"
    )
    time_spent_ratio = models.DecimalField(
        max_digits=4, decimal_places=3, default=0,
        help_text="0-1, actual time vs estimated time"
    )
    
    # Composite score
    difficulty_score = models.DecimalField(
        max_digits=4, decimal_places=3, default=0,
        help_text="0-1, higher = more difficult"
    )
    difficulty_level = models.CharField(
        max_length=20,
        choices=DifficultyLevel.choices,
        default=DifficultyLevel.UNKNOWN
    )
    
    # Statistics
    total_attempts = models.PositiveIntegerField(default=0)
    unique_students = models.PositiveIntegerField(default=0)
    total_views = models.PositiveIntegerField(default=0)
    
    # Metadata
    last_calculated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lesson_difficulty'
        indexes = [
            models.Index(fields=['difficulty_level']),
            models.Index(fields=['-difficulty_score']),
        ]
    
    def __str__(self):
        return f"{self.lesson.title}: {self.difficulty_level} ({self.difficulty_score})"


class Alert(models.Model):
    """
    System-generated alerts for teachers
    """
    class AlertType(models.TextChoices):
        DROPOUT_RISK = 'DROPOUT', 'Dropout Risk'
        PERFORMANCE_DROP = 'PERFORMANCE_DROP', 'Performance Drop'
        DISENGAGEMENT = 'DISENGAGEMENT', 'Disengagement'
        MULTIPLE_FAILURES = 'MULTIPLE_FAILURES', 'Multiple Failures'
        BEHIND_SCHEDULE = 'BEHIND_SCHEDULE', 'Behind Schedule'
        CUSTOM = 'CUSTOM', 'Custom Alert'

    class Severity(models.TextChoices):
        CRITICAL = 'CRITICAL', 'Critical'
        HIGH = 'HIGH', 'High'
        MEDIUM = 'MEDIUM', 'Medium'
        LOW = 'LOW', 'Low'
        INFO = 'INFO', 'Informational'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        ACKNOWLEDGED = 'ACKNOWLEDGED', 'Acknowledged'
        RESOLVED = 'RESOLVED', 'Resolved'
        DISMISSED = 'DISMISSED', 'Dismissed'
        EXPIRED = 'EXPIRED', 'Expired'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='alerts_received',
        limit_choices_to={'role': 'TEACHER'}
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='alerts_triggered',
        limit_choices_to={'role': 'STUDENT'}
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True
    )
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True
    )
    
    # Alert details
    alert_type = models.CharField(
        max_length=30,
        choices=AlertType.choices
    )
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.MEDIUM
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    
    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    recommendation = models.TextField(blank=True)
    
    # Data snapshot (store metrics at time of alert)
    risk_score = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True
    )
    engagement_score = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True
    )
    progress_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    
    # Timestamps
    generated_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Intervention tracking
    intervention_notes = models.TextField(blank=True)
    intervention_outcome = models.TextField(blank=True)
    
    class Meta:
        db_table = 'alerts'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['teacher', '-generated_at']),
            models.Index(fields=['student', 'status']),
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['alert_type']),
        ]
    
    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.student.display_name}: {self.status}"
    
    def acknowledge(self):
        """Mark alert as acknowledged"""
        self.status = self.Status.ACKNOWLEDGED
        self.acknowledged_at = timezone.now()
        self.save(update_fields=['status', 'acknowledged_at'])
    
    def resolve(self, outcome=""):
        """Mark alert as resolved"""
        self.status = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        if outcome:
            self.intervention_outcome = outcome
        self.save(update_fields=['status', 'resolved_at', 'intervention_outcome'])


class InterventionLog(models.Model):
    """
    Track teacher interventions and their effectiveness
    """
    class InterventionType(models.TextChoices):
        EMAIL = 'EMAIL', 'Email'
        MESSAGE = 'MESSAGE', 'In-app Message'
        MEETING = 'MEETING', 'One-on-One Meeting'
        RESOURCE = 'RESOURCE', 'Extra Resources'
        EXTENSION = 'EXTENSION', 'Deadline Extension'
        REMEDIATION = 'REMEDIATION', 'Remedial Assignment'
        OTHER = 'OTHER', 'Other'

    class Outcome(models.TextChoices):
        SUCCESSFUL = 'SUCCESS', 'Successful - Improved'
        PARTIAL = 'PARTIAL', 'Partial - Some Improvement'
        UNCHANGED = 'UNCHANGED', 'No Change'
        WORSENED = 'WORSENED', 'Worsened'
        UNKNOWN = 'UNKNOWN', 'Unknown'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='interventions_made'
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='interventions_received'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='interventions'
    )
    alert = models.ForeignKey(
        Alert,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interventions'
    )
    
    # Intervention details
    intervention_type = models.CharField(
        max_length=20,
        choices=InterventionType.choices
    )
    description = models.TextField()
    
    # Timing
    intervention_date = models.DateTimeField(default=timezone.now)
    follow_up_date = models.DateTimeField(null=True, blank=True)
    
    # Outcome
    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
        default=Outcome.UNKNOWN
    )
    outcome_notes = models.TextField(blank=True)
    
    # Effectiveness metrics
    risk_before = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True
    )
    risk_after = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True
    )
    improvement_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'intervention_log'
        ordering = ['-intervention_date']
        indexes = [
            models.Index(fields=['teacher', '-intervention_date']),
            models.Index(fields=['student', 'outcome']),
            models.Index(fields=['intervention_type']),
        ]
    
    def __str__(self):
        return f"{self.teacher.display_name} → {self.student.display_name}: {self.get_intervention_type_display()}"
    
    def calculate_improvement(self):
        """Calculate improvement percentage based on risk scores"""
        if self.risk_before and self.risk_after:
            if self.risk_before > 0:
                improvement = ((self.risk_before - self.risk_after) / self.risk_before) * 100
                self.improvement_percentage = Decimal(str(max(0, improvement)))
                self.save(update_fields=['improvement_percentage'])
                return self.improvement_percentage
        return None
    
class LessonInteraction(models.Model):
    """
    Track student interactions with lessons
    Used for engagement analytics and difficulty analysis
    """
    class InteractionType(models.TextChoices):
        VIEW = 'VIEW', 'Viewed'
        COMPLETE = 'COMPLETE', 'Completed'
        START = 'START', 'Started'
        PAUSE = 'PAUSE', 'Paused'
        REWIND = 'REWIND', 'Rewound'
        FORWARD = 'FORWARD', 'Forward'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='lesson_interactions'
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='interactions'
    )
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='lesson_interactions',
        null=True,
        blank=True
    )
    
    # Interaction details
    interaction_type = models.CharField(
        max_length=20,
        choices=InteractionType.choices
    )
    timestamp = models.DateTimeField(default=timezone.now)
    
    # For video/content tracking
    position_seconds = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(default=0)
    
    # Time-on-page tracking (Phase 1)
    time_on_page_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Seconds student spent on this lesson (tracked on exit/complete)"
    )
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'lesson_interactions'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['student', '-timestamp']),
            models.Index(fields=['lesson', 'interaction_type']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.student.display_name} - {self.lesson.title}: {self.interaction_type}"


class CompetencyPerformance(models.Model):
    """
    Track student performance on specific competencies.
    Aggregated from quiz attempt question-level data.
    Updated incrementally as students answer competency-tagged questions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    from courses.models import Competency
    
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='competency_performances'
    )
    competency = models.ForeignKey(
        Competency,
        on_delete=models.CASCADE,
        related_name='student_performances'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='competency_performances'
    )
    
    # Performance metrics
    score_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of correctly answered questions for this competency"
    )
    attempts_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of questions answered for this competency"
    )
    correct_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of questions answered correctly"
    )
    
    # Proficiency level
    proficiency_level = models.CharField(
        max_length=20,
        choices=[
            ('NOVICE', 'Novice'),
            ('DEVELOPING', 'Developing'),
            ('PROFICIENT', 'Proficient'),
            ('ADVANCED', 'Advanced'),
            ('UNKNOWN', 'Unknown')
        ],
        default='UNKNOWN',
        help_text="Proficiency level based on score_percentage"
    )
    
    # Metadata
    first_attempt_at = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'competency_performance'
        unique_together = ['student', 'competency', 'course']
        indexes = [
            models.Index(fields=['student', 'course']),
            models.Index(fields=['competency', 'proficiency_level']),
            models.Index(fields=['student', '-last_updated']),
        ]
    
    def __str__(self):
        return f"{self.student.display_name} - {self.competency.name}: {self.proficiency_level} ({self.score_percentage}%)"
    
    def update_proficiency_level(self):
        """Update proficiency level based on score thresholds"""
        score = float(self.score_percentage)
        if score < 30:
            self.proficiency_level = 'NOVICE'
        elif score < 60:
            self.proficiency_level = 'DEVELOPING'
        elif score < 85:
            self.proficiency_level = 'PROFICIENT'
        else:
            self.proficiency_level = 'ADVANCED'
        self.save(update_fields=['proficiency_level'])
