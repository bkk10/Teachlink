"""
Assessment and Quiz Management Models for TeachLink
- Quiz creation and management
- Question banks
- Student attempts and scoring
- Performance analytics
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from courses.models import Lesson
import uuid
import json

User = get_user_model()

class Quiz(models.Model):
    """
    Quiz/Assessment model linked to a lesson
    """
    class QuizType(models.TextChoices):
        MULTIPLE_CHOICE = 'MCQ', 'Multiple Choice'
        TRUE_FALSE = 'TF', 'True/False'
        MIXED = 'MIXED', 'Mixed Questions'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationship - One-to-One with Lesson
    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name='quiz',
        help_text="The lesson this quiz belongs to"
    )
    
    # Quiz metadata
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    quiz_type = models.CharField(
        max_length=20,
        choices=QuizType.choices,
        default=QuizType.MULTIPLE_CHOICE
    )
    
    # Quiz settings
    time_limit_minutes = models.PositiveIntegerField(
        default=0,
        help_text="0 = No time limit"
    )
    passing_score = models.PositiveIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum score percentage to pass"
    )
    max_attempts = models.PositiveIntegerField(
        default=3,
        help_text="Maximum number of attempts allowed"
    )
    shuffle_questions = models.BooleanField(default=False)
    show_answers = models.BooleanField(
        default=True,
        help_text="Show correct answers after completion"
    )
    
    # Status
    is_published = models.BooleanField(default=False)
    
    # Statistics (cached)
    total_questions = models.PositiveIntegerField(default=0)
    total_attempts = models.PositiveIntegerField(default=0)
    average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00
    )
    pass_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Percentage of attempts that passed"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'quizzes'
        indexes = [
            models.Index(fields=['lesson', 'is_published']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.lesson.title} - {self.title}"
    
    def update_statistics(self):
        """Update cached quiz statistics"""
        from django.db.models import Avg, Count, Q
        
        attempts = QuizAttempt.objects.filter(quiz=self)
        
        self.total_attempts = attempts.count()
        
        if self.total_attempts > 0:
            self.average_score = attempts.aggregate(
                Avg('score_percentage')
            )['score_percentage__avg'] or 0
            
            passed_attempts = attempts.filter(
                score_percentage__gte=self.passing_score
            ).count()
            self.pass_rate = (passed_attempts / self.total_attempts) * 100
        
        self.save(update_fields=['total_attempts', 'average_score', 'pass_rate'])


class Question(models.Model):
    """
    Question model for quizzes
    """
    class QuestionType(models.TextChoices):
        MULTIPLE_CHOICE = 'MCQ', 'Multiple Choice'
        TRUE_FALSE = 'TF', 'True/False'
        SHORT_ANSWER = 'SA', 'Short Answer'  # For future enhancement
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationship
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    
    # Question content
    question_type = models.CharField(
        max_length=10,
        choices=QuestionType.choices,
        default=QuestionType.MULTIPLE_CHOICE
    )
    text = models.TextField()
    
    # For true/false questions
    correct_answer = models.CharField(
        max_length=10,
        blank=True,
        help_text="For TF: 'true' or 'false'"
    )
    
    # Scoring
    points = models.PositiveIntegerField(default=1)
    
    # Metadata
    order = models.PositiveIntegerField(default=0)
    explanation = models.TextField(
        blank=True,
        help_text="Explanation of correct answer"
    )
    
    # Competency tagging (Phase 2)
    competencies = models.ManyToManyField(
        'courses.Competency',
        related_name='questions',
        blank=True,
        help_text="Competencies assessed by this question"
    )
    
    # Statistics (cached)
    times_answered = models.PositiveIntegerField(default=0)
    times_correct = models.PositiveIntegerField(default=0)
    difficulty_index = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        help_text="0.0 = Very Easy, 1.0 = Very Hard"
    )
    discrimination_index = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        help_text="Correlation with overall test performance"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'questions'
        ordering = ['order', 'created_at']
        unique_together = ['quiz', 'order']
        indexes = [
            models.Index(fields=['quiz', 'order']),
            models.Index(fields=['difficulty_index']),
        ]
    
    def __str__(self):
        return f"{self.quiz.title} - Q{self.order}: {self.text[:50]}"
    
    @property
    def correct_rate(self):
        """Percentage of times answered correctly"""
        if self.times_answered > 0:
            return (self.times_correct / self.times_answered) * 100
        return 0
    
    def update_difficulty(self):
        """Update difficulty index based on correct rate"""
        if self.times_answered > 0:
            # P = proportion correct (0-1)
            p = self.times_correct / self.times_answered
            # Transform to difficulty index (0-1)
            # 1 - p: 0 = all correct (easy), 1 = none correct (hard)
            self.difficulty_index = 1 - p
            self.save(update_fields=['difficulty_index'])


class Answer(models.Model):
    """
    Answer options for multiple choice questions
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationship
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    
    # Answer content
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    
    # Ordering
    order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'answers'
        ordering = ['order', 'created_at']
        unique_together = ['question', 'order']
        indexes = [
            models.Index(fields=['question', 'is_correct']),
        ]
    
    def __str__(self):
        return f"{self.question.text[:30]} - {self.text[:30]}"


class QuizAttempt(models.Model):
    """
    Student quiz attempt tracking
    """
    class Status(models.TextChoices):
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        TIMED_OUT = 'TIMED_OUT', 'Timed Out'
        ABANDONED = 'ABANDONED', 'Abandoned'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
        limit_choices_to={'role': 'STUDENT'}
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    
    # Attempt tracking
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS
    )
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)
    
    # Scoring
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00
    )
    score_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00
    )
    max_possible_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00
    )
    passed = models.BooleanField(default=False)
    
    # Answers stored as JSON for audit trail
    responses = models.JSONField(
        default=dict,
        help_text="Student's answers in format {question_id: answer_id or text}"
    )
    
    # Feedback
    feedback = models.TextField(blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'quiz_attempts'
        unique_together = ['student', 'quiz', 'attempt_number']
        indexes = [
            models.Index(fields=['student', 'quiz', '-started_at']),
            models.Index(fields=['quiz', 'passed']),
            models.Index(fields=['score_percentage']),
            models.Index(fields=['status', 'started_at']),
        ]
        ordering = ['-started_at']

    def save(self, *args, **kwargs):
            """Override save to validate enrollment"""
            # Check if this is a new attempt
            if not self.pk:
                from courses.models import Enrollment
                # Verify student is enrolled in the course
                if not Enrollment.objects.filter(
                    student=self.student,
                    course=self.quiz.lesson.module.course,
                    status='ACTIVE'
                ).exists():
                    raise ValidationError(
                        "Student must be enrolled in the course to attempt this quiz"
                    )
            
            super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.student.display_name} - {self.quiz.title} (Attempt {self.attempt_number})"
    
    def calculate_score(self):
        """
        Calculate score based on responses
        Returns: (score_earned, max_possible, percentage)
        """
        score_earned = 0
        max_possible = 0
        
        # Get all questions for this quiz
        questions = self.quiz.questions.all()
        
        for question in questions:
            max_possible += question.points
            response = self.responses.get(str(question.id))
            
            if response:
                try:
                    if question.question_type == Question.QuestionType.MULTIPLE_CHOICE:
                        # Response should be a UUID string
                        try:
                            # Validate UUID format
                            from uuid import UUID
                            UUID(str(response))
                            
                            # Get the answer
                            answer = Answer.objects.filter(
                                id=response, 
                                question=question
                            ).first()
                            
                            if answer and answer.is_correct:
                                score_earned += question.points
                        except (ValueError, TypeError):
                            # Invalid UUID format - skip this response
                            # Don't raise an exception, just skip
                            pass
                    
                    elif question.question_type == Question.QuestionType.TRUE_FALSE:
                        # Response should be 'true' or 'false'
                        if str(response).lower() == str(question.correct_answer).lower():
                            score_earned += question.points
                except Exception:
                    # Any other error - skip this response
                    pass
        
        self.score = score_earned
        self.max_possible_score = max_possible
        
        if max_possible > 0:
            self.score_percentage = (score_earned / max_possible) * 100
            # Cap at 100%
            if self.score_percentage > 100:
                self.score_percentage = 100
            self.passed = self.score_percentage >= self.quiz.passing_score
        
        return score_earned, max_possible, self.score_percentage

    def complete(self, responses=None):
        """Complete the quiz attempt"""
        # Check if already completed
        if self.status == self.Status.COMPLETED:
            raise ValueError("This attempt has already been completed")
        
        # Check time limit
        if self.quiz.time_limit_minutes > 0:
            elapsed = (timezone.now() - self.started_at).total_seconds() / 60
            if elapsed > self.quiz.time_limit_minutes:
                self.status = self.Status.TIMED_OUT
                self.save(update_fields=['status'])
                raise ValueError(f"Time limit exceeded. Elapsed: {elapsed:.1f} minutes, Limit: {self.quiz.time_limit_minutes} minutes")
            
        if responses:
            self.responses = responses
        
        self.calculate_score()
        self.status = self.Status.COMPLETED
        now_ts = timezone.now()
        # Guard against clock drift/data corruption: completion cannot predate start.
        if self.started_at and now_ts < self.started_at:
            self.submitted_at = self.started_at
        else:
            self.submitted_at = now_ts
        
        if self.started_at:
            delta = self.submitted_at - self.started_at
            self.time_spent_seconds = max(1, int(delta.total_seconds()))
        
        self.save()
        
        # Update question statistics
        self.update_question_statistics()
        
        # Update quiz statistics
        self.quiz.update_statistics()
        
        # Update enrollment performance
        self.update_enrollment_performance()
        
        return self.score_percentage
    
    def update_question_statistics(self):
        from django.db.models import F
        
        for question_id, answer in self.responses.items():
            try:
                question = Question.objects.get(id=question_id)
                
                # First, increment the counters using F() and save
                question.times_answered = F('times_answered') + 1
                
                if question.question_type == Question.QuestionType.MULTIPLE_CHOICE:
                    try:
                        answer_obj = Answer.objects.get(id=answer, question=question)
                        if answer_obj.is_correct:
                            question.times_correct = F('times_correct') + 1
                    except (Answer.DoesNotExist, ValueError):
                        pass
                
                elif question.question_type == Question.QuestionType.TRUE_FALSE:
                    if answer.lower() == question.correct_answer.lower():
                        question.times_correct = F('times_correct') + 1
                
                # Save the F() expressions
                question.save(update_fields=['times_answered', 'times_correct'])
                
                # Refresh from DB to get actual values, THEN update difficulty
                question.refresh_from_db()
                question.update_difficulty()
                
            except (Question.DoesNotExist, ValidationError, ValueError, TypeError):
                continue
    
    def update_enrollment_performance(self):
        """Update student's enrollment average quiz score"""
        from courses.models import Enrollment
        
        try:
            enrollment = Enrollment.objects.get(
                student=self.student,
                course=self.quiz.lesson.module.course
            )
            
            # Calculate new average quiz score
            all_attempts = QuizAttempt.objects.filter(
                student=self.student,
                quiz__lesson__module__course=enrollment.course,
                status=QuizAttempt.Status.COMPLETED
            )
            
            avg_score = all_attempts.aggregate(
                models.Avg('score_percentage')
            )['score_percentage__avg'] or 0
            
            enrollment.average_quiz_score = avg_score
            enrollment.save(update_fields=['average_quiz_score'])
            
        except Enrollment.DoesNotExist:
            pass


class QuestionResponse(models.Model):
    """
    Detailed response tracking for analytics
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='question_responses'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    
    # Response
    selected_answer_id = models.UUIDField(null=True, blank=True)
    selected_answer_text = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)
    
    # Timing
    time_spent_seconds = models.PositiveIntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'question_responses'
        unique_together = ['attempt', 'question']
        indexes = [
            models.Index(fields=['attempt', 'question']),
            models.Index(fields=['question', 'is_correct']),
        ]
    
    def __str__(self):
        return f"{self.attempt} - Q{self.question.order}"
