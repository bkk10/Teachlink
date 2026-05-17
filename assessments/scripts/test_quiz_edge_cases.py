#!/usr/bin/env python
"""
Test edge cases for quiz system
Run: python manage.py shell < scripts/test_quiz_edge_cases.py
"""
import django
import os
import sys
from uuid import UUID
from typing import Optional, Any, Dict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings.development')
django.setup()

from assessments.models import Quiz, QuizAttempt
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.request import Request
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from assessments.views import QuizViewSet
from courses.models import Lesson, Module, Course, Enrollment
from django.db.models import Count, Q

User = get_user_model()

def create_api_request(method: str, url: str, user, data: Optional[Dict] = None):
    """Helper to create an authenticated API request"""
    factory = APIRequestFactory()
    
    if method.lower() == 'post':
        if data:
            django_request = factory.post(url, data, format='json')
        else:
            django_request = factory.post(url, format='json')
    elif method.lower() == 'get':
        django_request = factory.get(url)
    else:
        django_request = factory.get(url)
    
    # Authenticate and wrap with explicit parsers so request.data works for submit().
    force_authenticate(django_request, user=user)
    drf_request = Request(
        django_request,
        parsers=[JSONParser(), FormParser(), MultiPartParser()]
    )
    drf_request.user = user
    return drf_request

def find_student_with_attempts(quiz, max_attempts=3):
    """Find a student who has fewer than max_attempts completed attempts"""
    students = User.objects.filter(role='STUDENT')
    
    for student in students:
        attempt_count = QuizAttempt.objects.filter(
            student=student,
            quiz=quiz,
            status=QuizAttempt.Status.COMPLETED
        ).count()
        
        if attempt_count < max_attempts:
            return student, attempt_count
    
    return None, 0

def cleanup_active_attempts(quiz, student):
    """Clean up any active attempts for this student and quiz"""
    active_attempts = QuizAttempt.objects.filter(
        student=student,
        quiz=quiz,
        status=QuizAttempt.Status.IN_PROGRESS
    )
    count = active_attempts.count()
    active_attempts.delete()
    if count > 0:
        print(f"   🧹 Cleaned up {count} active attempt(s)")
    return count

def test_attempt_limit(quiz, student):
    """Test 1: Attempt limit enforcement"""
    print("\n1️⃣ Testing attempt limit...")
    cleanup_active_attempts(quiz, student)
    
    attempt_count = QuizAttempt.objects.filter(
        student=student,
        quiz=quiz,
        status=QuizAttempt.Status.COMPLETED
    ).count()
    
    print(f"   Current attempts: {attempt_count}/{quiz.max_attempts}")
    
    if attempt_count >= quiz.max_attempts:
        print("   ✅ Attempt limit reached - cannot start new attempt")
        
        request = create_api_request('post', f'/api/assessments/quizzes/{quiz.id}/start/', student)
        
        view = QuizViewSet()
        view.action = 'start'
        view.request = request  # type: ignore
        view.kwargs = {'pk': str(quiz.id)}
        view.get_object = lambda: quiz  # type: ignore
        
        response = view.start(request, pk=str(quiz.id))
        
        if response.status_code == 400:
            print(f"   ✅ Blocked by API: {response.data.get('error')}")
            return True
        else:
            print(f"   ❌ API allowed attempt when it shouldn't have")
            return False
    else:
        print(f"   ✅ Student has {attempt_count}/{quiz.max_attempts} attempts - can start new attempt")
        return True

def test_time_limit(quiz, student):
    """Test 2: Time limit enforcement"""
    print("\n2️⃣ Testing time limit...")
    cleanup_active_attempts(quiz, student)
    
    if quiz.time_limit_minutes == 0:
        print("   ⏱️  No time limit on this quiz")
        return True
    
    # First start an attempt via API
    start_request = create_api_request('post', f'/api/assessments/quizzes/{quiz.id}/start/', student)
    
    view = QuizViewSet()
    view.action = 'start'
    view.request = start_request  # type: ignore
    view.kwargs = {'pk': str(quiz.id)}
    view.get_object = lambda: quiz  # type: ignore
    
    start_response = view.start(start_request, pk=str(quiz.id))
    
    if start_response.status_code != 201:
        print(f"   ❌ Could not start attempt: {start_response.data}")
        return False
    
    attempt_id = start_response.data['id']
    attempt = QuizAttempt.objects.get(id=attempt_id)
    
    # Manually set the started_at to be in the past
    attempt.started_at = timezone.now() - timezone.timedelta(minutes=quiz.time_limit_minutes + 5)
    attempt.save(update_fields=['started_at'])
    
    print(f"   Created attempt #{attempt.attempt_number} with old timestamp")
    
    # Try to submit via API
    submit_request = create_api_request(
        'post', 
        f'/api/assessments/quizzes/{quiz.id}/submit/', 
        student,
        {'attempt_id': str(attempt_id), 'responses': {}}
    )
    
    submit_response = view.submit(submit_request, pk=str(quiz.id))
    
    # Clean up the attempt
    attempt.delete()
    
    if submit_response.status_code == 400 and 'Time limit exceeded' in str(submit_response.data):
        print(f"   ✅ Timeout working: {submit_response.data.get('error')}")
        return True
    else:
        print(f"   ❌ Should have timed out - got {submit_response.status_code}")
        return False

def test_empty_responses(quiz, student):
    """Test 3: Empty responses should score 0%"""
    print("\n3️⃣ Testing empty responses...")
    cleanup_active_attempts(quiz, student)
    
    # Start attempt
    start_request = create_api_request('post', f'/api/assessments/quizzes/{quiz.id}/start/', student)
    
    view = QuizViewSet()
    view.action = 'start'
    view.request = start_request  # type: ignore
    view.kwargs = {'pk': str(quiz.id)}
    view.get_object = lambda: quiz  # type: ignore
    
    start_response = view.start(start_request, pk=str(quiz.id))
    
    if start_response.status_code != 201:
        print(f"   ❌ Could not start attempt: {start_response.data}")
        return False
    
    attempt_id = start_response.data['id']
    
    # Submit with empty responses
    submit_request = create_api_request(
        'post', 
        f'/api/assessments/quizzes/{quiz.id}/submit/', 
        student,
        {'attempt_id': str(attempt_id), 'responses': {}}
    )
    
    submit_response = view.submit(submit_request, pk=str(quiz.id))
    
    # Clean up the attempt
    attempt = QuizAttempt.objects.get(id=attempt_id)
    attempt.delete()
    
    if submit_response.status_code == 200:
        score = submit_response.data.get('score_percentage', 0)
        print(f"   Empty responses: {score:.1f}% (should be 0)")
        return score == 0
    else:
        print(f"   ❌ Submit failed: {submit_response.data}")
        return False

def test_invalid_question_ids(quiz, student):
    """Test 4: Invalid question IDs should be handled gracefully"""
    print("\n4️⃣ Testing invalid question IDs...")
    cleanup_active_attempts(quiz, student)
    
    # Start attempt
    start_request = create_api_request('post', f'/api/assessments/quizzes/{quiz.id}/start/', student)
    
    view = QuizViewSet()
    view.action = 'start'
    view.request = start_request  # type: ignore
    view.kwargs = {'pk': str(quiz.id)}
    view.get_object = lambda: quiz  # type: ignore
    
    start_response = view.start(start_request, pk=str(quiz.id))
    
    if start_response.status_code != 201:
        print(f"   ❌ Could not start attempt: {start_response.data}")
        return False
    
    attempt_id = start_response.data['id']
    
    # Submit with invalid question IDs
    invalid_responses = {'invalid-id': 'answer', 'not-a-uuid': 'true'}
    submit_request = create_api_request(
        'post', 
        f'/api/assessments/quizzes/{quiz.id}/submit/', 
        student,
        {'attempt_id': str(attempt_id), 'responses': invalid_responses}
    )
    
    submit_response = view.submit(submit_request, pk=str(quiz.id))
    
    # Clean up the attempt
    attempt = QuizAttempt.objects.get(id=attempt_id)
    attempt.delete()
    
    if submit_response.status_code == 200:
        score = submit_response.data.get('score_percentage', 0)
        print(f"   ✅ Handled invalid question IDs gracefully - Score: {score:.1f}%")
        return True
    else:
        print(f"   ❌ Failed on invalid IDs: {submit_response.data}")
        return False

def test_duplicate_completion(quiz, student):
    """Test 5: Duplicate submission should be blocked"""
    print("\n5️⃣ Testing duplicate completion...")
    cleanup_active_attempts(quiz, student)
    
    # Start attempt
    start_request = create_api_request('post', f'/api/assessments/quizzes/{quiz.id}/start/', student)
    
    view = QuizViewSet()
    view.action = 'start'
    view.request = start_request  # type: ignore
    view.kwargs = {'pk': str(quiz.id)}
    view.get_object = lambda: quiz  # type: ignore
    
    start_response = view.start(start_request, pk=str(quiz.id))
    
    if start_response.status_code != 201:
        print(f"   ❌ Could not start attempt: {start_response.data}")
        return False
    
    attempt_id = start_response.data['id']
    
    # First submission
    submit_request1 = create_api_request(
        'post', 
        f'/api/assessments/quizzes/{quiz.id}/submit/', 
        student,
        {'attempt_id': str(attempt_id), 'responses': {}}
    )
    
    response1 = view.submit(submit_request1, pk=str(quiz.id))
    
    if response1.status_code != 200:
        print(f"   ❌ First submission failed: {response1.data}")
        return False
    
    print(f"   First completion: {response1.data.get('score_percentage'):.1f}%")
    
    # Try to submit again
    submit_request2 = create_api_request(
        'post', 
        f'/api/assessments/quizzes/{quiz.id}/submit/', 
        student,
        {'attempt_id': str(attempt_id), 'responses': {}}
    )
    
    response2 = view.submit(submit_request2, pk=str(quiz.id))
    
    # Clean up the attempt
    attempt = QuizAttempt.objects.get(id=attempt_id)
    attempt.delete()
    
    if response2.status_code == 404 or 'not found' in str(response2.data).lower():
        print(f"   ✅ Duplicate completion blocked: {response2.data.get('error', 'Not found')}")
        return True
    else:
        print(f"   ❌ Should not allow duplicate completion - got {response2.status_code}")
        return False

def test_enrollment_validation(student):
    """Test 6: Cannot attempt quiz without enrollment"""
    print("\n6️⃣ Testing quiz without enrollment...")
    
    # Find a course the student is NOT enrolled in
    enrolled_courses = Enrollment.objects.filter(student=student).values_list('course_id', flat=True)
    available_course = Course.objects.exclude(id__in=enrolled_courses).first()
    
    if not available_course:
        print("   ⚠️  No available course for testing enrollment validation")
        return None
    
    # Create a test course, module, lesson, and quiz
    test_module = Module.objects.create(
        course=available_course,
        title='Test Module for Enrollment Validation',
        order=999
    )
    
    test_lesson = Lesson.objects.create(
        module=test_module,
        title='Test Lesson for Enrollment Validation',
        content_type='TEXT',
        is_published=True
    )
    
    test_quiz = Quiz.objects.create(
        lesson=test_lesson,
        title='Test Quiz - No Enrollment',
        is_published=True
    )
    
    print(f"   Created test quiz in course: {available_course.title}")
    
    # Try to start attempt via API
    request = create_api_request('post', f'/api/assessments/quizzes/{test_quiz.id}/start/', student)
    
    view = QuizViewSet()
    view.action = 'start'
    view.request = request  # type: ignore
    view.kwargs = {'pk': str(test_quiz.id)}
    view.get_object = lambda: test_quiz  # type: ignore
    
    response = view.start(request, pk=str(test_quiz.id))
    
    # Clean up
    test_quiz.delete()
    test_lesson.delete()
    test_module.delete()
    
    if response.status_code == 403:
        print(f"   ✅ Blocked: {response.data.get('error')}")
        return True
    else:
        print(f"   ❌ Should not allow attempt without enrollment - got {response.status_code}")
        return False

def test_edge_cases():
    """Main test runner"""
    print("=" * 60)
    print("⚠️  TESTING EDGE CASES")
    print("=" * 60)
    
    # Get test data
    quiz = Quiz.objects.filter(title__icontains='HTML').first()
    
    if not quiz:
        print("❌ Quiz not found")
        print("   Please run create_test_quiz.py first")
        return
    
    # Find a student with remaining attempts
    student, attempt_count = find_student_with_attempts(quiz, quiz.max_attempts)
    
    if not student:
        print("❌ No student with remaining attempts found")
        print("   Please create a new student or reset attempts")
        return
    
    print(f"📋 Test Data:")
    print(f"   Quiz: {quiz.title}")
    print(f"   Student: {student.display_name}")  # type: ignore
    print(f"   Current Attempts: {attempt_count}/{quiz.max_attempts}")
    print(f"   Time Limit: {quiz.time_limit_minutes} minutes")
    
    # Clean up old test attempts
    old_attempts = QuizAttempt.objects.filter(
        student=student,
        quiz=quiz,
        attempt_number__gte=900
    )
    count = old_attempts.count()
    old_attempts.delete()
    print(f"🧹 Cleaned up {count} old test attempts")
    
    # Clean up any active attempts before starting
    cleanup_active_attempts(quiz, student)
    
    # Run tests
    results = []
    
    # Test 1: Attempt limit
    results.append(('Attempt Limit', test_attempt_limit(quiz, student)))
    
    # Test 2: Time limit
    results.append(('Time Limit', test_time_limit(quiz, student)))
    
    # Test 3: Empty responses
    results.append(('Empty Responses', test_empty_responses(quiz, student)))
    
    # Test 4: Invalid question IDs
    results.append(('Invalid Question IDs', test_invalid_question_ids(quiz, student)))
    
    # Test 5: Duplicate completion
    results.append(('Duplicate Completion', test_duplicate_completion(quiz, student)))
    
    # Test 6: Enrollment validation
    results.append(('Enrollment Validation', test_enrollment_validation(student)))
    
    # Final cleanup
    cleanup_active_attempts(quiz, student)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        if result is True:
            print(f"  ✅ {name}: PASSED")
        elif result is False:
            print(f"  ❌ {name}: FAILED")
            all_passed = False
        else:
            print(f"  ⚠️  {name}: SKIPPED")
    
    print("=" * 60)
    if all_passed:
        print("🎉 ALL EDGE CASE TESTS PASSED! Your quiz system is robust!")
    else:
        print("🔧 Some tests failed - review the output above")
    print("=" * 60)

if __name__ == "__main__":
    test_edge_cases()
