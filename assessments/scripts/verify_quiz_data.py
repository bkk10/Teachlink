#!/usr/bin/env python
"""
Verify quiz data and statistics
Run: python manage.py shell < scripts/verify_quiz_data.py
"""
import django
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings.development')
django.setup()

from assessments.models import Quiz, Question, Answer, QuizAttempt
from courses.models import Enrollment
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count

User = get_user_model()

def verify_quiz_data():
    print("=" * 60)
    print("🔍 VERIFYING QUIZ DATA AND STATISTICS")
    print("=" * 60)
    
    # 1. Quiz statistics
    quiz = Quiz.objects.filter(title__icontains='HTML').first()
    if quiz:
        print(f"\n📊 QUIZ: {quiz.title}")
        print(f"   ID: {quiz.id}")
        print(f"   Published: {quiz.is_published}")
        print(f"   Questions: {quiz.total_questions}")
        print(f"   Total Attempts: {quiz.total_attempts}")
        print(f"   Average Score: {quiz.average_score:.1f}%")
        print(f"   Pass Rate: {quiz.pass_rate:.1f}%")
        
        # 2. Questions breakdown
        print(f"\n📝 QUESTIONS:")
        for q in quiz.questions.all().order_by('order'):
            print(f"   Q{q.order}: {q.text[:50]}...")
            print(f"      Type: {q.question_type}, Points: {q.points}")
            print(f"      Times answered: {q.times_answered}, Correct: {q.times_correct}")
            print(f"      Difficulty: {q.difficulty_index:.2f} (0=easy, 1=hard)")
            print(f"      Correct rate: {q.correct_rate:.1f}%")
            
            if q.question_type == 'MCQ':
                correct = q.answers.filter(is_correct=True).first()
                print(f"      ✅ Correct: {correct.text if correct else 'N/A'}")
            print()
    
    # 3. Attempt statistics
    attempts = QuizAttempt.objects.filter(quiz=quiz)
    print(f"\n🎯 ATTEMPTS: {attempts.count()} total")
    
    if attempts.exists():
        print(f"   Completed: {attempts.filter(status='COMPLETED').count()}")
        print(f"   In Progress: {attempts.filter(status='IN_PROGRESS').count()}")
        print(f"   Passed: {attempts.filter(passed=True).count()}")
        print(f"   Failed: {attempts.filter(passed=False, status='COMPLETED').count()}")
        
        # 4. Student performance
        print(f"\n👨‍🎓 STUDENT PERFORMANCE:")
        student_attempts = attempts.values('student__display_name').annotate(
            avg_score=Avg('score_percentage'),
            attempt_count=Count('id'),
            best_score=Avg('score_percentage')  # Simplified
        ).order_by('-avg_score')
        
        for sa in student_attempts[:5]:
            print(f"   {sa['student__display_name']}:")
            print(f"      Attempts: {sa['attempt_count']}")
            print(f"      Avg Score: {sa['avg_score']:.1f}%")
    
    # 5. Enrollment impact
    print(f"\n📈 ENROLLMENT IMPACT:")
    if quiz:
        course = quiz.lesson.module.course
        enrollments = Enrollment.objects.filter(course=course)
        
        for enrollment in enrollments[:5]:
            print(f"   {enrollment.student.display_name}:")
            print(f"      Course: {enrollment.course.title}")
            print(f"      Avg Quiz Score: {enrollment.average_quiz_score:.1f}%")
            print(f"      Progress: {enrollment.progress_percentage:.1f}%")
            print(f"      Risk Level: {enrollment.risk_level}")
    
    print("\n" + "=" * 60)
    print("✅ VERIFICATION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    verify_quiz_data()