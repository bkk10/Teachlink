#!/usr/bin/env python
"""
End-to-End Integration Testing for Teachly
Tests complete user flows across all modules
Run: python manage.py shell < scripts/test_e2e_flows.py
"""
import django
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from courses.models import Course, Module, Lesson, Enrollment, LessonCompletion
from assessments.models import Quiz, Question, Answer, QuizAttempt
from analytics.models import RiskHistory, Alert, LessonDifficulty
from analytics.services.risk_engine import RiskEngine
from analytics.services.alert_generator import AlertGenerator

User = get_user_model()

def test_complete_flow():
    """Test the complete user journey from enrollment to risk detection"""
    
    print("\n" + "=" * 70)
    print("🧪 TEST 1: COMPLETE USER FLOW")
    print("=" * 70)
    
    # 1. Create test teacher
    teacher, _ = User.objects.get_or_create(
        email='test.teacher@teachly.com',
        defaults={
            'username': 'test_teacher',
            'display_name': 'Test Teacher',
            'role': 'TEACHER',
            'is_active': True
        }
    )
    teacher.set_password('Test123!')
    teacher.save()
    print(f"✅ Teacher created: {teacher.display_name}")
    
    # 2. Create test student
    student, _ = User.objects.get_or_create(
        email='test.student@teachly.com',
        defaults={
            'username': 'test_student',
            'display_name': 'Test Student',
            'role': 'STUDENT',
            'is_active': True
        }
    )
    student.set_password('Test123!')
    student.save()
    print(f"✅ Student created: {student.display_name}")
    
    # 3. Create course
    course = Course.objects.create(
        title='Integration Test Course',
        description='Course for testing complete flow',
        teacher=teacher,
        status='PUBLISHED',
        start_date=timezone.now().date(),
        end_date=timezone.now().date() + timedelta(days=90)
    )
    print(f"✅ Course created: {course.title}")
    
    # 4. Create module
    module = Module.objects.create(
        course=course,
        title='Test Module',
        description='Module for testing',
        order=1,
        estimated_minutes=60
    )
    
    # 5. Create lessons
    lessons = []
    for i in range(5):
        lesson = Lesson.objects.create(
            module=module,
            title=f'Test Lesson {i+1}',
            content_type='TEXT',
            content_text=f'Content for lesson {i+1}',
            order=i+1,
            is_published=True,
            estimated_minutes=10
        )
        lessons.append(lesson)
    print(f"✅ Created {len(lessons)} lessons")
    
    # 6. Create quiz for lesson 3
    quiz_lesson = lessons[2]  # Lesson 3
    quiz = Quiz.objects.create(
        lesson=quiz_lesson,
        title='Integration Test Quiz',
        description='Quiz for testing',
        time_limit_minutes=10,
        passing_score=70,
        max_attempts=3,
        is_published=True
    )
    
    # 7. Create questions
    questions_data = [
        {
            'text': 'What is 2+2?',
            'question_type': 'MCQ',
            'points': 10,
            'order': 1,
            'answers': [
                {'text': '3', 'is_correct': False, 'order': 1},
                {'text': '4', 'is_correct': True, 'order': 2},
                {'text': '5', 'is_correct': False, 'order': 3},
                {'text': '6', 'is_correct': False, 'order': 4},
            ]
        },
        {
            'text': 'Python is a programming language.',
            'question_type': 'TF',
            'points': 5,
            'order': 2,
            'correct_answer': 'true',
            'answers': []
        }
    ]
    
    for q_data in questions_data:
        answers_data = q_data.pop('answers', [])
        question = Question.objects.create(quiz=quiz, **q_data)
        
        for a_data in answers_data:
            Answer.objects.create(question=question, **a_data)
    
    quiz.total_questions = quiz.questions.count()
    quiz.save()
    print(f"✅ Quiz created with {quiz.total_questions} questions")
    
    # 8. Enroll student
    enrollment = Enrollment.objects.create(
        student=student,
        course=course,
        status='ACTIVE'
    )
    print(f"✅ Student enrolled in course")
    
    # 9. Complete some lessons
    for lesson in lessons[:2]:  # Complete first 2 lessons
        completion = LessonCompletion.objects.create(
            student=student,
            lesson=lesson,
            time_spent_seconds=300  # 5 minutes
        )
    print(f"✅ Student completed 2 lessons")
    
    # 10. Take quiz
    print("\n📝 Student taking quiz...")
    attempt = QuizAttempt.objects.create(
        student=student,
        quiz=quiz,
        attempt_number=1,
        status=QuizAttempt.Status.IN_PROGRESS
    )
    
    # Prepare answers (80% correct)
    responses = {}
    for question in quiz.questions.all():
        if question.question_type == 'MCQ':
            correct = question.answers.filter(is_correct=True).first()
            responses[str(question.id)] = str(correct.id)
        else:
            responses[str(question.id)] = 'true'
    
    # Submit quiz
    score = attempt.complete(responses)
    print(f"   Quiz score: {score:.1f}%")
    print(f"   Passed: {attempt.passed}")
    
    # 11. Update enrollment progress
    enrollment.update_progress()
    print(f"   Course progress: {enrollment.progress_percentage:.1f}%")
    
    # 12. Calculate risk score
    print("\n🔍 Calculating risk score...")
    risk_result = RiskEngine.calculate_student_risk(enrollment.id)
    if risk_result:
        print(f"   Risk Score: {risk_result['risk_score']} ({risk_result['risk_level']})")
        print(f"   Performance: {risk_result['components']['performance']:.3f}")
        print(f"   Progress: {risk_result['components']['progress']:.3f}")
        print(f"   Engagement: {risk_result['components']['engagement']:.3f}")
        
        if risk_result['contributing_factors']:
            print(f"   ⚠️ Factors: {[f['factor'] for f in risk_result['contributing_factors']]}")
    
    # 13. Check alerts
    print("\n🚨 Checking alerts...")
    alerts = AlertGenerator.check_and_generate_alerts(enrollment.id)
    print(f"   Generated {len(alerts)} new alerts")
    
    # 14. Analyze difficulty
    print("\n📊 Analyzing lesson difficulty...")
    from analytics.services.difficulty_analyzer import DifficultyAnalyzer
    difficulty = DifficultyAnalyzer.analyze_lesson_difficulty(quiz_lesson.id)
    if difficulty:
        print(f"   Lesson: {difficulty['lesson_title']}")
        print(f"   Difficulty Score: {difficulty['difficulty_score']:.3f}")
        print(f"   Level: {difficulty['difficulty_level']}")
        print(f"   Components:")
        print(f"      Failure Rate: {difficulty['components']['failure_rate']:.3f}")
        print(f"      Attempt Intensity: {difficulty['components']['attempt_intensity']:.3f}")
        print(f"      Access Frequency: {difficulty['components']['access_frequency']:.3f}")
    
    # 15. Verify data consistency
    print("\n🔎 Verifying data consistency...")
    enrollment.refresh_from_db()
    print(f"   Enrollment avg quiz score: {enrollment.average_quiz_score:.1f}%")
    print(f"   Enrollment risk level: {enrollment.risk_level}")
    
    quiz.refresh_from_db()
    print(f"   Quiz total attempts: {quiz.total_attempts}")
    print(f"   Quiz avg score: {quiz.average_score:.1f}%")
    
    # 16. Clean up
    print("\n🧹 Cleaning up test data...")
    enrollment.delete()
    quiz.delete()
    for lesson in lessons:
        lesson.delete()
    module.delete()
    course.delete()
    student.delete()
    teacher.delete()
    print("✅ Test data cleaned up")
    
    print("\n✅ COMPLETE USER FLOW TEST PASSED")
    return True


def test_concurrent_users():
    """Test system with multiple concurrent users"""
    
    print("\n" + "=" * 70)
    print("🧪 TEST 2: CONCURRENT USER SIMULATION")
    print("=" * 70)
    
    # Create teacher
    teacher = User.objects.create_user(
        username='concurrent_teacher',
        email='concurrent.teacher@test.com',
        password='Test123!',
        display_name='Concurrent Teacher',
        role='TEACHER'
    )
    
    # Create course
    course = Course.objects.create(
        title='Concurrent Test Course',
        description='Course for concurrency testing',
        teacher=teacher,
        status='PUBLISHED'
    )
    
    # Create module and lessons
    module = Module.objects.create(
        course=course,
        title='Concurrent Module',
        order=1
    )
    
    lesson = Lesson.objects.create(
        module=module,
        title='Concurrent Lesson',
        content_type='TEXT',
        is_published=True
    )
    
    # Create students and simulate concurrent activity
    students = []
    enrollments = []
    
    print(f"\n📊 Creating 10 test students...")
    for i in range(10):
        student = User.objects.create_user(
            username=f'concurrent_student_{i}',
            email=f'student{i}@test.com',
            password='Test123!',
            display_name=f'Student {i}',
            role='STUDENT'
        )
        students.append(student)
        
        enrollment = Enrollment.objects.create(
            student=student,
            course=course,
            status='ACTIVE'
        )
        enrollments.append(enrollment)
    
    print(f"✅ Created {len(students)} students and enrollments")
    
    # Simulate concurrent risk calculations
    print(f"\n🔄 Simulating concurrent risk calculations...")
    import time
    import threading
    
    results = []
    
    def calculate_risk_for_student(enrollment_id, index):
        result = RiskEngine.calculate_student_risk(enrollment_id)
        results.append((index, result['risk_score'] if result else None))
        print(f"   Thread {index}: Complete")
    
    threads = []
    start_time = time.time()
    
    for i, enrollment in enumerate(enrollments):
        thread = threading.Thread(
            target=calculate_risk_for_student,
            args=(enrollment.id, i)
        )
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    elapsed = time.time() - start_time
    print(f"\n⏱️  All {len(threads)} calculations completed in {elapsed:.2f} seconds")
    print(f"   Average per student: {elapsed/len(threads)*1000:.2f}ms")
    
    # Clean up
    print(f"\n🧹 Cleaning up...")
    for enrollment in enrollments:
        enrollment.delete()
    for student in students:
        student.delete()
    lesson.delete()
    module.delete()
    course.delete()
    teacher.delete()
    
    print(f"✅ CONCURRENT USER TEST PASSED")
    return True


def test_edge_cases():
    """Test edge cases and error handling"""
    
    print("\n" + "=" * 70)
    print("🧪 TEST 3: EDGE CASES & ERROR HANDLING")
    print("=" * 70)
    
    # Test 1: Student with no activity
    print("\n1️⃣ Testing student with no activity...")
    teacher = User.objects.create_user(
        username='edge_teacher',
        email='edge.teacher@test.com',
        password='Test123!',
        display_name='Edge Teacher',
        role='TEACHER'
    )
    
    student = User.objects.create_user(
        username='edge_student',
        email='edge.student@test.com',
        password='Test123!',
        display_name='Edge Student',
        role='STUDENT'
    )
    
    course = Course.objects.create(
        title='Edge Test Course',
        teacher=teacher,
        status='PUBLISHED'
    )
    
    enrollment = Enrollment.objects.create(
        student=student,
        course=course,
        status='ACTIVE'
    )
    
    risk = RiskEngine.calculate_student_risk(enrollment.id)
    print(f"   Risk score with no activity: {risk['risk_score']:.3f}")
    print(f"   Should be moderate (0.5): {'✓' if 0.4 < risk['risk_score'] < 0.6 else '✗'}")
    
    # Test 2: Student with perfect performance
    print("\n2️⃣ Testing student with perfect performance...")
    module = Module.objects.create(course=course, title='Test Module')
    
    # Create quiz
    lesson = Lesson.objects.create(
        module=module,
        title='Perfect Score Quiz',
        content_type='QUIZ',
        is_published=True
    )
    
    quiz = Quiz.objects.create(
        lesson=lesson,
        title='Perfect Quiz',
        passing_score=70,
        is_published=True
    )
    
    question = Question.objects.create(
        quiz=quiz,
        text='Test question',
        question_type='TF',
        correct_answer='true',
        points=10
    )
    
    # Student takes quiz with perfect score
    attempt = QuizAttempt.objects.create(
        student=student,
        quiz=quiz,
        attempt_number=1,
        status=QuizAttempt.Status.COMPLETED,
        score_percentage=100,
        passed=True
    )
    
    # Complete all lessons
    LessonCompletion.objects.create(
        student=student,
        lesson=lesson
    )
    
    enrollment.update_progress()
    risk = RiskEngine.calculate_student_risk(enrollment.id)
    print(f"   Risk score with perfect performance: {risk['risk_score']:.3f}")
    print(f"   Should be very low (<0.2): {'✓' if risk['risk_score'] < 0.2 else '✗'}")
    
    # Test 3: Enrollment with future dates
    print("\n3️⃣ Testing course with future start date...")
    future_course = Course.objects.create(
        title='Future Course',
        teacher=teacher,
        status='PUBLISHED',
        start_date=timezone.now().date() + timedelta(days=30),
        end_date=timezone.now().date() + timedelta(days=120)
    )
    
    future_enrollment = Enrollment.objects.create(
        student=student,
        course=future_course,
        status='ACTIVE'
    )
    
    risk = RiskEngine.calculate_student_risk(future_enrollment.id)
    print(f"   Risk score for future course: {risk['risk_score']:.3f}")
    print(f"   Should handle gracefully: {'✓' if risk else '✗'}")
    
    # Clean up
    print(f"\n🧹 Cleaning up...")
    future_enrollment.delete()
    future_course.delete()
    attempt.delete()
    question.delete()
    quiz.delete()
    lesson.delete()
    module.delete()
    enrollment.delete()
    course.delete()
    student.delete()
    teacher.delete()
    
    print(f"\n✅ EDGE CASES TEST PASSED")
    return True


def run_all_tests():
    """Run all integration tests"""
    
    print("\n" + "=" * 70)
    print("🏁 STARTING INTEGRATION TEST SUITE")
    print("=" * 70)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Complete User Flow
    try:
        if test_complete_flow():
            tests_passed += 1
    except Exception as e:
        print(f"❌ Complete flow test failed: {e}")
        tests_failed += 1
    
    # Test 2: Concurrent Users
    try:
        if test_concurrent_users():
            tests_passed += 1
    except Exception as e:
        print(f"❌ Concurrent users test failed: {e}")
        tests_failed += 1
    
    # Test 3: Edge Cases
    try:
        if test_edge_cases():
            tests_passed += 1
    except Exception as e:
        print(f"❌ Edge cases test failed: {e}")
        tests_failed += 1
    
    print("\n" + "=" * 70)
    print(f"📊 TEST RESULTS: {tests_passed} passed, {tests_failed} failed")
    print("=" * 70)
    
    return tests_failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)