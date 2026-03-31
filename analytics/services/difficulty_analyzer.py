"""
Difficulty Analyzer Service
Identifies difficult topics based on student performance and behavior
"""
from decimal import Decimal
from django.db.models import Avg, Count, Min, Max
from courses.models import Lesson, LessonCompletion
from assessments.models import QuizAttempt
from analytics.models import LessonDifficulty, LessonInteraction
from typing import Optional, Dict, Any, List

class DifficultyAnalyzer:
    """
    Analyzes lesson difficulty using updated inputs:
    - Quiz attempts per lesson
    - Failed quiz attempts
    - Lesson re-access count
    """
    
    @classmethod
    def analyze_lesson_difficulty(cls, lesson_id: str) -> Optional[Dict[str, Any]]:
        """
        Calculate comprehensive difficulty score for a lesson
        """
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return None
        
        # Get or create difficulty record
        difficulty, created = LessonDifficulty.objects.get_or_create(
            lesson=lesson
        )
        
        # 1. Calculate failed attempts ratio
        failure_rate = cls._calculate_failure_rate(lesson)
        difficulty.failure_rate = Decimal(str(failure_rate))
        
        # 2. Calculate attempts per student intensity
        attempt_intensity = cls._calculate_attempt_intensity(lesson)
        difficulty.attempt_intensity = Decimal(str(attempt_intensity))
        
        # 3. Calculate re-access intensity (stored in existing access_frequency field)
        reaccess_intensity = cls._calculate_reaccess_intensity(lesson)
        difficulty.access_frequency = Decimal(str(reaccess_intensity))
        
        # Ancillary metric retained for observability
        time_spent_ratio = cls._calculate_time_spent_ratio(lesson)
        difficulty.time_spent_ratio = Decimal(str(time_spent_ratio))
        
        # Updated weighted composite
        difficulty_score = (
            failure_rate * 0.40 +
            attempt_intensity * 0.30 +
            reaccess_intensity * 0.30
        )

        difficulty.difficulty_score = Decimal(str(min(1.0, difficulty_score)))
        
        # Use the more conservative (higher) of weighted score or failure_rate_only classification
        weighted_classification = cls._determine_difficulty_classification(difficulty_score)
        failure_classification = cls._determine_difficulty_from_failure_rate(failure_rate)
        
        # Map classifications to numeric for comparison: LOW=0, MEDIUM=1, HIGH=2
        classification_rank = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2}
        more_conservative = max(weighted_classification, failure_classification, 
                               key=lambda x: classification_rank.get(x, 0))
        difficulty_classification = more_conservative
        
        difficulty.difficulty_level = cls._map_to_lesson_difficulty_level(difficulty_classification)
        
        # Update statistics
        difficulty.total_views = cls._get_total_views(lesson)
        difficulty.unique_students = cls._get_unique_students(lesson)
        difficulty.total_attempts = cls._get_total_attempts(lesson)
        
        difficulty.save()
        
        # Update lesson model
        lesson.difficulty_score = difficulty.difficulty_score
        lesson.difficulty_level = difficulty_classification
        lesson.save(update_fields=['difficulty_score', 'difficulty_level'])
        
        return {
            'lesson_id': str(lesson.id),
            'lesson_title': lesson.title,
            'difficulty_score': float(difficulty.difficulty_score),
            'difficulty_level': difficulty.difficulty_level,
            'difficulty_classification': difficulty_classification,
            'components': {
                'failure_rate': float(failure_rate),
                'attempt_intensity': float(attempt_intensity),
                'reaccess_intensity': float(reaccess_intensity),
                'reaccess_count': cls._get_reaccess_count(lesson),
                'time_spent_ratio': float(time_spent_ratio),
            },
            'statistics': {
                'total_views': difficulty.total_views,
                'unique_students': difficulty.unique_students,
                'total_attempts': difficulty.total_attempts,
                'failed_attempts': cls._get_failed_attempts(lesson),
            }
        }
    
    @classmethod
    def _calculate_failure_rate(cls, lesson: Lesson) -> float:
        """
        Calculate proportion of students who failed the quiz
        """
        if not hasattr(lesson, 'quiz'):
            return 0.0
        
        quiz = lesson.quiz
        
        # Get all completed attempts
        attempts = QuizAttempt.objects.filter(
            quiz=quiz,
            status=QuizAttempt.Status.COMPLETED
        )
        
        total_attempts = attempts.count()
        if total_attempts == 0:
            return 0.0
        
        # Count failed attempts (score < passing_score)
        failed_attempts = attempts.filter(
            score_percentage__lt=quiz.passing_score
        ).count()
        
        return failed_attempts / total_attempts
    
    @classmethod
    def _calculate_attempt_intensity(cls, lesson: Lesson) -> float:
        """
        Calculate average attempts per student
        Normalized to 0-1 where 3+ attempts = 1.0
        """
        if not hasattr(lesson, 'quiz'):
            return 0.0
        
        quiz = lesson.quiz
        
        # Get attempts per student
        student_attempts = QuizAttempt.objects.filter(
            quiz=quiz,
            status=QuizAttempt.Status.COMPLETED
        ).values('student').annotate(
            attempt_count=Count('id')
        )
        
        if not student_attempts:
            return 0.0
        
        total_students = student_attempts.count()
        total_attempts = sum(s['attempt_count'] for s in student_attempts)
        
        if total_students == 0:
            return 0.0
        
        avg_attempts = total_attempts / total_students
        
        # Normalize: 0 attempts = 0, 3+ attempts = 1
        return min(1.0, avg_attempts / 3.0)
    
    @classmethod
    def _calculate_reaccess_intensity(cls, lesson: Lesson) -> float:
        """
        Calculate lesson re-access intensity with struggle weighting.
        Re-access count is the number of extra lesson views beyond first view per student.
        Students who re-access and fail to improve quiz scores increase this signal.
        """
        view_counts = cls._get_view_counts(lesson)
        unique_viewers = len(view_counts)
        if unique_viewers == 0:
            return 0.0

        # Base re-access intensity from view repeats.
        reaccess_count = cls._get_reaccess_count(lesson)
        avg_reaccess_per_viewer = reaccess_count / unique_viewers
        # 2+ re-accesses per viewer is treated as max intensity.
        base_intensity = min(1.0, avg_reaccess_per_viewer / 2.0)

        # Struggle multiplier: re-access + no quiz improvement
        struggle_ratio = cls._calculate_struggle_reaccess_ratio(lesson)
        weighted = base_intensity * (0.7 + (0.3 * struggle_ratio))
        return min(1.0, weighted)
    
    @classmethod
    def _calculate_time_spent_ratio(cls, lesson: Lesson) -> float:
        """
        Calculate actual time spent vs estimated time
        """
        completions = LessonCompletion.objects.filter(
            lesson=lesson,
            time_spent_seconds__gt=0
        )
        
        if not completions.exists():
            return 1.0
        
        avg_time_spent = completions.aggregate(
            Avg('time_spent_seconds')
        )['time_spent_seconds__avg']
        
        if lesson.estimated_minutes > 0:
            estimated_seconds = lesson.estimated_minutes * 60
            return avg_time_spent / estimated_seconds
        
        return 1.0
    
    @classmethod
    def _get_total_views(cls, lesson: Lesson) -> int:
        """
        Get total number of lesson views.
        If interaction logs are missing, count lesson completions as at least one view.
        """
        return sum(cls._get_view_counts(lesson).values())

    @classmethod
    def _get_reaccess_count(cls, lesson: Lesson) -> int:
        """
        Total re-access count:
        sum(max(0, views_per_student - 1)) across students.
        """
        view_counts = cls._get_view_counts(lesson)
        return sum(max(0, count - 1) for count in view_counts.values())
    
    @classmethod
    def _get_unique_students(cls, lesson: Lesson) -> int:
        """Get unique students who viewed/completed or attempted quizzes."""
        student_ids = set(cls._get_view_counts(lesson).keys())
        if hasattr(lesson, 'quiz'):
            attempt_student_ids = QuizAttempt.objects.filter(
                quiz=lesson.quiz,
                status=QuizAttempt.Status.COMPLETED
            ).values_list('student_id', flat=True).distinct()
            student_ids.update(attempt_student_ids)
        return len(student_ids)
    
    @classmethod
    def _get_total_attempts(cls, lesson: Lesson) -> int:
        """Get total quiz attempts"""
        if hasattr(lesson, 'quiz'):
            return QuizAttempt.objects.filter(
                quiz=lesson.quiz
            ).count()
        return 0

    @classmethod
    def _get_failed_attempts(cls, lesson: Lesson) -> int:
        """Get total failed quiz attempts for lesson."""
        if not hasattr(lesson, 'quiz'):
            return 0
        return QuizAttempt.objects.filter(
            quiz=lesson.quiz,
            status=QuizAttempt.Status.COMPLETED,
            score_percentage__lt=lesson.quiz.passing_score
        ).count()

    @classmethod
    def _calculate_struggle_reaccess_ratio(cls, lesson: Lesson) -> float:
        """
        Ratio of re-accessing students who do not improve quiz score.
        Improvement is defined as max_score > min_score across completed attempts.
        """
        if not hasattr(lesson, 'quiz'):
            return 0.0

        view_counts = cls._get_view_counts(lesson)
        student_ids = [student_id for student_id, count in view_counts.items() if count > 1]
        if not student_ids:
            return 0.0

        attempts_by_student = QuizAttempt.objects.filter(
            quiz=lesson.quiz,
            status=QuizAttempt.Status.COMPLETED,
            student_id__in=student_ids
        ).values('student').annotate(
            min_score=Min('score_percentage'),
            max_score=Max('score_percentage'),
            attempts=Count('id'),
        )

        no_improvement = 0
        total = 0
        for row in attempts_by_student:
            total += 1
            improved = row['max_score'] > row['min_score']
            if not improved:
                no_improvement += 1

        # If there are no quiz attempts among reaccessing students, treat as no clear struggle signal.
        if total == 0:
            return 0.0
        return no_improvement / total

    @classmethod
    def _get_view_counts(cls, lesson: Lesson) -> Dict[Any, int]:
        """
        Build per-student view counts.
        Falls back to lesson completion records when explicit VIEW interactions are missing.
        """
        counts: Dict[Any, int] = {}
        for row in LessonInteraction.objects.filter(
            lesson=lesson,
            interaction_type=LessonInteraction.InteractionType.VIEW
        ).values('student').annotate(view_count=Count('id')):
            counts[row['student']] = int(row['view_count'] or 0)

        # Ensure completed students register at least one access.
        completion_students = LessonCompletion.objects.filter(
            lesson=lesson
        ).values_list('student_id', flat=True).distinct()
        for student_id in completion_students:
            counts[student_id] = max(counts.get(student_id, 0), 1)

        return counts
    
    @classmethod
    def _determine_difficulty_classification(cls, score: float) -> str:
        """3-band classification based on weighted difficulty score."""
        # Align with user-specified thresholds:
        # 0-30% => LOW, 30-60% => MEDIUM, 60-100% => HIGH
        if score < 0.30:
            return 'LOW'
        elif score < 0.60:
            return 'MEDIUM'
        return 'HIGH'
    
    @classmethod
    def _determine_difficulty_from_failure_rate(cls, failure_rate: float) -> str:
        """Direct classification based on failure rate only.
        User's suggested thresholds:
        < 30% = LOW, 30-60% = MEDIUM, > 60% = HIGH
        """
        if failure_rate < 0.30:
            return 'LOW'
        elif failure_rate < 0.60:
            return 'MEDIUM'
        return 'HIGH'

    @classmethod
    def _map_to_lesson_difficulty_level(cls, classification: str) -> str:
        """
        Map 3-band classification to existing LessonDifficulty choices.
        Keeps DB schema unchanged while supporting new model semantics.
        """
        mapping = {
            'LOW': LessonDifficulty.DifficultyLevel.LOW,
            'MEDIUM': LessonDifficulty.DifficultyLevel.MEDIUM,
            'HIGH': LessonDifficulty.DifficultyLevel.HIGH,
        }
        return mapping.get(classification, LessonDifficulty.DifficultyLevel.UNKNOWN)
    
    @classmethod
    def analyze_course_difficulties(cls, course_id: str) -> List[Dict[str, Any]]:
        """
        Analyze difficulty for all lessons in a course
        """
        lessons = Lesson.objects.filter(
            module__course_id=course_id,
            is_published=True
        )
        
        results = []
        for lesson in lessons:
            result = cls.analyze_lesson_difficulty(str(lesson.id))
            if result:
                results.append(result)
        
        # Sort by difficulty score (highest first)
        results.sort(key=lambda x: x['difficulty_score'], reverse=True)
        
        return results
    
    @classmethod
    def get_hardest_lessons(cls, course_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the hardest lessons across all courses or specific course
        """
        queryset = LessonDifficulty.objects.all()
        
        if course_id:
            queryset = queryset.filter(lesson__module__course_id=course_id)
        
        hardest = queryset.order_by('-difficulty_score')[:limit]
        
        return [
            {
                'lesson_id': str(d.lesson.id),
                'lesson_title': d.lesson.title,
                'course_title': d.lesson.module.course.title,
                'difficulty_score': float(d.difficulty_score),
                'difficulty_level': d.difficulty_level,
                'failure_rate': float(d.failure_rate),
                'attempt_intensity': float(d.attempt_intensity),
                'access_frequency': float(d.access_frequency),
                'reaccess_intensity': float(d.access_frequency),
                'difficulty_classification': cls._determine_difficulty_classification(float(d.difficulty_score)),
                'total_attempts': d.total_attempts,
                'unique_students': d.unique_students
            }
            for d in hardest
        ]
