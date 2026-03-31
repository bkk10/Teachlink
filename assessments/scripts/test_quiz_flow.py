#!/usr/bin/env python
"""
Test the complete quiz attempt flow
Run: python manage.py shell < scripts/test_quiz_flow.py
"""
import django
import os
import sys
import json
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachlink.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from courses.models import Course, Enrollment
from assessments.models import Quiz, Question, Answer, QuizAttempt
from django.utils import timezone

User = get_user_model()

def test_quiz_flow():
    print("=" * 60)
    print("🧪 TESTING QUIZ ATTEMPT FLOW")
    print("=" * 60)
    
    # 1. Get a student
    student = User.objects.filter(role='STUDENT').first()
    if not student:
        print("❌ No student found. Please run seed script first.")
        return
    print(f"✅ Using student: {student.display_name} ({student.email})")
    
    # 2. Get the quiz we created
    quiz = Quiz.objects.filter(title='HTML Fundamentals Quiz').first()
    if not quiz:
        print("❌ Quiz not found. Please run create_test_quiz.py first.")
        return
    print(f"✅ Using quiz: {quiz.title} (ID: {quiz.id})")
    print(f"   Questions: {quiz.total_questions}")
    print(f"   Passing Score: {quiz.passing_score}%")
    
    # 3. Ensure student is enrolled in the course
    course = quiz.lesson.module.course
    enrollment, created = Enrollment.objects.get_or_create(
        student=student,
        course=course,
        defaults={'status': 'ACTIVE'}
    )
    if created:
        print(f"✅ Enrolled student in course: {course.title}")
    else:
        print(f"✅ Student already enrolled in course: {course.title}")
    
    # 4. Check attempts remaining
    attempt_count = QuizAttempt.objects.filter(
        student=student,
        quiz=quiz,
        status=QuizAttempt.Status.COMPLETED
    ).count()
    
    attempts_left = quiz.max_attempts - attempt_count
    print(f"📊 Attempts: {attempt_count} used, {attempts_left} remaining")
    
    # 5. Start a new attempt
    print("\n" + "-" * 40)
    print("🚀 Starting new quiz attempt...")
    
    attempt = QuizAttempt.objects.create(
        student=student,
        quiz=quiz,
        attempt_number=attempt_count + 1,
        status=QuizAttempt.Status.IN_PROGRESS,
        ip_address='127.0.0.1',
        user_agent='Test Script'
    )
    
    print(f"✅ Attempt created: #{attempt.attempt_number}")
    print(f"   Attempt ID: {attempt.id}")
    print(f"   Started at: {attempt.started_at}")
    
    # 6. Prepare answers (80% correct - aiming to pass)
    print("\n" + "-" * 40)
    print("📝 Preparing answers (80% correct)...")
    
    responses = {}
    questions = quiz.questions.all().order_by('order')
    
    for i, question in enumerate(questions):
        if question.question_type == 'MCQ':
            # Get correct answer
            correct_answer = question.answers.filter(is_correct=True).first()
            # For questions 3 and 8, choose wrong answer to test scoring
            if question.order in [3, 8]:  # Wrong answers for these questions
                wrong_answer = question.answers.filter(is_correct=False).first()
                responses[str(question.id)] = str(wrong_answer.id)
                print(f"   Q{question.order}: ❌ Wrong answer (intentional)")
            else:
                responses[str(question.id)] = str(correct_answer.id)
                print(f"   Q{question.order}: ✅ Correct answer")
                
        elif question.question_type == 'TF':
            if question.order == 6:  # "HTML is a programming language" - False
                responses[str(question.id)] = 'false'
                print(f"   Q{question.order}: ✅ Correct answer (false)")
            elif question.order == 10:  # "Java and JavaScript same" - False
                responses[str(question.id)] = 'false'
                print(f"   Q{question.order}: ✅ Correct answer (false)")
            else:
                responses[str(question.id)] = 'true'
                print(f"   Q{question.order}: ✅ Correct answer")
    
    # 7. Submit the attempt
    print("\n" + "-" * 40)
    print("📤 Submitting quiz attempt...")
    
    # Simulate time spent (5 minutes)
    attempt.submitted_at = attempt.started_at + timezone.timedelta(minutes=5)
    
    # Complete the attempt
    score_percentage = attempt.complete(responses)
    
    print(f"\n📊 RESULTS:")
    print(f"   Score: {attempt.score:.2f} / {attempt.max_possible_score:.2f}")
    print(f"   Percentage: {score_percentage:.1f}%")
    print(f"   Passed: {'✅ YES' if attempt.passed else '❌ NO'}")
    print(f"   Time spent: {attempt.time_spent_seconds} seconds")
    
    # 8. Verify enrollment performance update
    enrollment.refresh_from_db()
    print(f"\n📈 ENROLLMENT UPDATE:")
    print(f"   Course: {enrollment.course.title}")
    print(f"   Student: {enrollment.student.display_name}")
    print(f"   Average Quiz Score: {enrollment.average_quiz_score:.1f}%")
    print(f"   Progress: {enrollment.progress_percentage:.1f}%")
    print(f"   Risk Level: {enrollment.risk_level}")
    
    # 9. Test second attempt with perfect score
    print("\n" + "-" * 40)
    print("🚀 Starting SECOND attempt (perfect score)...")
    
    attempt2 = QuizAttempt.objects.create(
        student=student,
        quiz=quiz,
        attempt_number=attempt_count + 2,
        status=QuizAttempt.Status.IN_PROGRESS,
        ip_address='127.0.0.1',
        user_agent='Test Script'
    )
    
    # Perfect answers
    perfect_responses = {}
    for question in questions:
        if question.question_type == 'MCQ':
            correct_answer = question.answers.filter(is_correct=True).first()
            perfect_responses[str(question.id)] = str(correct_answer.id)
        elif question.question_type == 'TF':
            perfect_responses[str(question.id)] = question.correct_answer
    
    # Submit perfect attempt
    attempt2.submitted_at = attempt2.started_at + timezone.timedelta(minutes=4)
    perfect_score = attempt2.complete(perfect_responses)
    
    print(f"\n📊 SECOND ATTEMPT RESULTS:")
    print(f"   Score: {attempt2.score:.2f} / {attempt2.max_possible_score:.2f}")
    print(f"   Percentage: {perfect_score:.1f}%")
    print(f"   Passed: {'✅ YES' if attempt2.passed else '❌ NO'}")
    
    # 10. Check updated enrollment average
    enrollment.refresh_from_db()
    print(f"\n📈 UPDATED ENROLLMENT AVERAGE:")
    print(f"   New Average Quiz Score: {enrollment.average_quiz_score:.1f}%")
    
    # 11. Test attempt limit
    print("\n" + "-" * 40)
    print("🔒 Testing attempt limit...")
    
    attempt3_count = QuizAttempt.objects.filter(
        student=student,
        quiz=quiz,
        status=QuizAttempt.Status.COMPLETED
    ).count()
    
    if attempt3_count >= quiz.max_attempts:
        print(f"❌ Cannot start attempt {attempt3_count + 1}: Maximum attempts ({quiz.max_attempts}) reached")
    else:
        print(f"✅ Can start attempt {attempt3_count + 1}")
    
    # 12. Display quiz statistics
    quiz.refresh_from_db()
    print(f"\n📊 QUIZ STATISTICS:")
    print(f"   Total Attempts: {quiz.total_attempts}")
    print(f"   Average Score: {quiz.average_score:.1f}%")
    print(f"   Pass Rate: {quiz.pass_rate:.1f}%")
    
    print("\n" + "=" * 60)
    print("✅ QUIZ FLOW TEST COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    
    return {
        'quiz': quiz,
        'attempts': [attempt, attempt2],
        'enrollment': enrollment
    }

if __name__ == "__main__":
    results = test_quiz_flow()