"""
CSV Import History Models for TeachLink
Tracks CSV import operations, audit logs, and individual imported records
"""
from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class ImportHistory(models.Model):
    """
    Audit log for CSV import operations
    Tracks who imported what, when, and the results
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        PARTIAL = 'PARTIAL', 'Partial Success'
        ROLLED_BACK = 'ROLLED_BACK', 'Rolled Back'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Who performed the import
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='csv_imports',
        limit_choices_to={'role__in': ['TEACHER', 'ADMIN']}
    )
    
    # Which course this import belongs to
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='csv_imports',
        null=True,
        blank=True
    )
    
    # Import metadata
    file_name = models.CharField(max_length=255)
    original_file = models.FileField(
        upload_to='csv_imports/%Y/%m/%d/',
        help_text="Stored original CSV file for audit trail"
    )
    
    # Import statistics
    total_records = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    # Processing details
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    processing_time_seconds = models.PositiveIntegerField(null=True, blank=True)
    
    # Error details (JSON for flexibility)
    error_log = models.JSONField(
        default=list,
        help_text="List of errors encountered during import"
    )
    
    # Rollback tracking
    is_rolled_back = models.BooleanField(default=False)
    rolled_back_at = models.DateTimeField(null=True, blank=True)
    rolled_back_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rolled_back_imports'
    )
    
    # Risk recalculation tracking
    students_affected = models.JSONField(
        default=list,
        help_text="List of student IDs whose risk scores were recalculated"
    )
    risk_recalculated = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'csv_import_history'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['teacher', '-started_at']),
            models.Index(fields=['course', '-started_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.file_name} by {self.teacher.display_name} ({self.status})"
    
    @property
    def success_rate(self):
        """Calculate percentage of successful imports"""
        if self.total_records == 0:
            return 0
        return round((self.success_count / self.total_records) * 100, 1)
    
    def mark_completed(self):
        """Mark import as completed with timestamp"""
        from django.utils import timezone
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        if self.started_at:
            self.processing_time_seconds = int(
                (self.completed_at - self.started_at).total_seconds()
            )
        self.save(update_fields=['status', 'completed_at', 'processing_time_seconds', 
                                 'total_records', 'success_count', 'error_count', 'warning_count',
                                 'students_affected', 'risk_recalculated'])
    
    def mark_failed(self, error_message):
        """Mark import as failed with error details"""
        from django.utils import timezone
        self.status = self.Status.FAILED
        self.completed_at = timezone.now()
        self.error_log.append({
            'timestamp': timezone.now().isoformat(),
            'error': error_message
        })
        self.save(update_fields=['status', 'completed_at', 'error_log'])
    
    def rollback(self, user):
        """Rollback this import - delete all associated records"""
        from django.utils import timezone
        
        # Delete all associated import records
        deleted_count = self.records.all().delete()[0]
        
        # Delete associated quiz attempts
        for record in self.records.all():
            if record.attempt:
                record.attempt.delete()
        
        self.is_rolled_back = True
        self.rolled_back_at = timezone.now()
        self.rolled_back_by = user
        self.status = self.Status.ROLLED_BACK
        self.save(update_fields=['is_rolled_back', 'rolled_back_at', 'rolled_back_by', 'status'])
        
        return deleted_count


class ImportRecord(models.Model):
    """
    Individual record imported via CSV
    Links import history to actual quiz attempts
    """
    class Status(models.TextChoices):
        SUCCESS = 'SUCCESS', 'Success'
        ERROR = 'ERROR', 'Error'
        WARNING = 'WARNING', 'Warning'
        SKIPPED = 'SKIPPED', 'Skipped'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to parent import
    import_history = models.ForeignKey(
        ImportHistory,
        on_delete=models.CASCADE,
        related_name='records'
    )
    
    # Original CSV data
    row_number = models.PositiveIntegerField()
    raw_data = models.JSONField(help_text="Original CSV row data")
    
    # Parsed data
    student_email = models.CharField(max_length=255)
    assessment_name = models.CharField(max_length=255)
    score = models.DecimalField(max_digits=5, decimal_places=2)
    date = models.DateField()
    
    # Status and result
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUCCESS
    )
    message = models.TextField(blank=True, help_text="Error message or success note")
    
    # Links to actual database records
    student = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='imported_attempts'
    )
    quiz = models.ForeignKey(
        'assessments.Quiz',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='imported_attempts'
    )
    attempt = models.ForeignKey(
        'assessments.QuizAttempt',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_record'
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # For edit tracking
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='edited_import_records'
    )
    original_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Original score before edit"
    )
    
    class Meta:
        db_table = 'csv_import_records'
        ordering = ['row_number']
        indexes = [
            models.Index(fields=['import_history', 'status']),
            models.Index(fields=['student_email']),
            models.Index(fields=['assessment_name']),
        ]
    
    def __str__(self):
        return f"Row {self.row_number}: {self.student_email} - {self.assessment_name} ({self.status})"
    
    def edit_score(self, new_score, edited_by_user):
        """
        Edit the imported score and update related quiz attempt
        """
        from django.utils import timezone
        
        # Store original score if not already stored
        if self.original_score is None:
            self.original_score = self.score
        
        # Update score
        self.score = new_score
        self.is_edited = True
        self.edited_at = timezone.now()
        self.edited_by = edited_by_user
        
        # Update the associated quiz attempt
        if self.attempt:
            self.attempt.score_percentage = new_score
            self.attempt.score = (new_score / 100) * self.attempt.max_possible_score
            self.attempt.save(update_fields=['score_percentage', 'score'])
            
            # Recalculate risk for the student
            self.attempt.update_enrollment_performance()
        
        self.save(update_fields=[
            'score', 'original_score', 'is_edited', 
            'edited_at', 'edited_by'
        ])
    
    def delete_record(self):
        """
        Delete this import record and its associated quiz attempt
        """
        if self.attempt:
            # Delete the quiz attempt (this will trigger risk recalculation)
            self.attempt.delete()
        
        # Update parent import statistics
        parent = self.import_history
        if self.status == self.Status.SUCCESS:
            parent.success_count = max(0, parent.success_count - 1)
        parent.save(update_fields=['success_count'])
        
        # Delete this record
        self.delete()
