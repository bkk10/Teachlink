"""
Script to retroactively create LessonInteraction VIEW records for imported quiz attempts.
This fixes the access count bug where imported scores showed failure rates but 0 access counts.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

django.setup()

from django.utils import timezone
from assessments.models import QuizAttempt, ImportRecord
from analytics.models import LessonInteraction

def fix_missing_lesson_interactions():
    """
    Find all imported quiz attempts that don't have corresponding LessonInteraction VIEW records,
    then create the missing interaction records.
    """
    print("=" * 60)
    print("FIXING MISSING LESSON INTERACTIONS FOR IMPORTED ATTEMPTS")
    print("=" * 60)
    
    # Find all imported quiz attempts
    imported_attempts = QuizAttempt.objects.filter(
        responses__source='csv'
    ).select_related('quiz', 'quiz__lesson', 'student')
    
    print(f"\nFound {imported_attempts.count()} imported quiz attempts")
    
    created_count = 0
    skipped_count = 0
    
    for attempt in imported_attempts:
        # Check if VIEW interaction already exists
        existing = LessonInteraction.objects.filter(
            student=attempt.student,
            lesson=attempt.quiz.lesson,
            interaction_type=LessonInteraction.InteractionType.VIEW
        ).exists()
        
        if existing:
            skipped_count += 1
            continue
        
        # Create the missing VIEW interaction
        try:
            LessonInteraction.objects.create(
                student=attempt.student,
                lesson=attempt.quiz.lesson,
                interaction_type=LessonInteraction.InteractionType.VIEW,
                timestamp=attempt.submitted_at or timezone.now()
            )
            created_count += 1
            print(f"  ✓ Created VIEW interaction: {attempt.student.email} - {attempt.quiz.lesson.title}")
        except Exception as e:
            print(f"  ✗ Failed to create interaction for {attempt.student.email}: {e}")
    
    print(f"\n{'=' * 60}")
    print("FIX COMPLETE")
    print(f"{'=' * 60}")
    print(f"Created: {created_count} lesson interactions")
    print(f"Skipped (already existed): {skipped_count}")
    print(f"Total processed: {imported_attempts.count()}")

if __name__ == '__main__':
    fix_missing_lesson_interactions()
