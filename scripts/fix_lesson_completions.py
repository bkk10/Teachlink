"""
Script to retroactively complete lessons for students who passed quizzes.
This fixes the issue where progress is stuck at 10% despite quiz passes.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

django.setup()

from django.utils import timezone
from assessments.models import QuizAttempt
from courses.models import LessonCompletion, Lesson, Enrollment

def fix_missing_lesson_completions():
    """
    Find all students who passed quizzes but don't have the lesson marked complete,
    then create the lesson completion records and update progress.
    """
    print("=" * 60)
    print("FIXING MISSING LESSON COMPLETIONS")
    print("=" * 60)
    
    # Find all passed quiz attempts
    passed_attempts = QuizAttempt.objects.filter(
        passed=True,
        status=QuizAttempt.Status.COMPLETED
    ).select_related('quiz', 'quiz__lesson', 'student')
    
    print(f"\nFound {passed_attempts.count()} passed quiz attempts")
    
    fixed_count = 0
    progress_updates = []
    
    for attempt in passed_attempts:
        student = attempt.student
        quiz = attempt.quiz
        lesson = quiz.lesson
        
        # Check if lesson completion already exists
        completion_exists = LessonCompletion.objects.filter(
            student=student,
            lesson=lesson
        ).exists()
        
        if not completion_exists:
            # Create lesson completion
            completion = LessonCompletion.objects.create(
                student=student,
                lesson=lesson,
                completed_at=attempt.submitted_at or timezone.now(),
                time_spent_seconds=quiz.time_limit_minutes * 60 if quiz.time_limit_minutes else 1800
            )
            print(f"  ✓ Created completion: {student.email} - {lesson.title}")
            fixed_count += 1
            
            # Track unique student-course pairs for progress update
            course = lesson.module.course
            key = (str(student.id), str(course.id))
            if key not in progress_updates:
                progress_updates.append(key)
    
    print(f"\nCreated {fixed_count} missing lesson completions")
    
    # Update progress for affected students
    print(f"\nUpdating progress for {len(progress_updates)} student-course pairs...")
    
    for student_id, course_id in progress_updates:
        try:
            enrollment = Enrollment.objects.get(
                student_id=student_id,
                course_id=course_id,
                status='ACTIVE'
            )
            old_progress = enrollment.progress_percentage
            enrollment.update_progress()
            new_progress = enrollment.progress_percentage
            print(f"  ✓ {enrollment.student.email}: {old_progress:.1f}% → {new_progress:.1f}%")
        except Enrollment.DoesNotExist:
            print(f"  ✗ No active enrollment found for student {student_id} in course {course_id}")
        except Exception as e:
            print(f"  ✗ Error updating progress: {e}")
    
    print("\n" + "=" * 60)
    print("FIX COMPLETE")
    print("=" * 60)
    print(f"Fixed {fixed_count} lesson completions")
    print(f"Updated progress for {len(progress_updates)} enrollments")

if __name__ == '__main__':
    fix_missing_lesson_completions()
