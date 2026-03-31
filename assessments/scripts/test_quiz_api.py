#!/usr/bin/env python
"""
Test Quiz API endpoints using requests
Run: python scripts/test_quiz_api.py
"""
import requests
import json
from pprint import pprint

BASE_URL = "http://localhost:8000/api"

def test_quiz_api():
    print("=" * 60)
    print("🌐 TESTING QUIZ API ENDPOINTS")
    print("=" * 60)
    
    # 1. Login as student
    print("\n1️⃣ Logging in as student...")
    login_response = requests.post(
        f"{BASE_URL}/auth/login/",
        json={
            "email": "james.kamau@student.com",
            "password": "Student123!"
        }
    )
    
    if login_response.status_code != 200:
        print("❌ Student login failed. Trying Peter...")
        login_response = requests.post(
            f"{BASE_URL}/auth/login/",
            json={
                "email": "peter.odhiambo@student.com",
                "password": "Student123!"
            }
        )
    
    if login_response.status_code == 200:
        student_token = login_response.json()['access']
        print("✅ Student login successful")
    else:
        print(f"❌ Student login failed: {login_response.text}")
        return
    
    # 2. Login as teacher
    print("\n2️⃣ Logging in as teacher...")
    teacher_login = requests.post(
        f"{BASE_URL}/auth/login/",
        json={
            "email": "mr_ochieng@teachlink.com",
            "password": "Teacher123!"
        }
    )
    
    if teacher_login.status_code == 200:
        teacher_token = teacher_login.json()['access']
        print("✅ Teacher login successful")
    else:
        print(f"❌ Teacher login failed: {teacher_login.text}")
        return
    
    # 3. Get available quizzes (student view)
    print("\n3️⃣ Fetching available quizzes (student)...")
    headers = {"Authorization": f"Bearer {student_token}"}
    quizzes_response = requests.get(
        f"{BASE_URL}/assessments/quizzes/",
        headers=headers
    )
    
    quiz_id = None  # 👈 INITIALIZE HERE!
    
    if quizzes_response.status_code == 200:
        quizzes = quizzes_response.json()
        print(f"✅ Found {len(quizzes)} quizzes")
        
        for quiz in quizzes:
            print(f"   - {quiz.get('title')} (ID: {quiz.get('id')})")
            if 'HTML Fundamentals' in quiz.get('title', ''):
                quiz_id = quiz.get('id')
    else:
        print(f"❌ Failed to fetch quizzes: {quizzes_response.text}")
    
    # 4. Get quiz details (student view - no correct answers)
    print("\n4️⃣ Fetching quiz details (student view)...")
    if quiz_id:  # 👈 NOW THIS IS SAFE
        detail_response = requests.get(
            f"{BASE_URL}/assessments/quizzes/{quiz_id}/",
            headers=headers
        )
        
        if detail_response.status_code == 200:
            quiz_detail = detail_response.json()
            print(f"✅ Quiz: {quiz_detail.get('title')}")
            print(f"   Questions: {len(quiz_detail.get('questions', []))}")
            print(f"   Attempts remaining: {quiz_detail.get('attempts_remaining')}")
            print(f"   Best score: {quiz_detail.get('best_score')}%")
            
            # Show first question without correct answer
            if quiz_detail.get('questions'):
                q = quiz_detail['questions'][0]
                print(f"\n   Sample question (no correct answer shown):")
                print(f"   Q: {q.get('text')}")
                print(f"   Answers: {[a.get('text') for a in q.get('answers', [])]}")
        else:
            print(f"❌ Failed to fetch quiz details: {detail_response.text}")
    else:
        print("⚠️ No quiz found with 'HTML' in title, skipping quiz detail test")
    
    # 5. Get quiz details (teacher view - with correct answers)
    print("\n5️⃣ Fetching quiz details (teacher view)...")
    headers_teacher = {"Authorization": f"Bearer {teacher_token}"}
    
    if quiz_id:  # 👈 NOW THIS IS SAFE
        teacher_detail = requests.get(
            f"{BASE_URL}/assessments/quizzes/{quiz_id}/",
            headers=headers_teacher
        )
        
        if teacher_detail.status_code == 200:
            quiz_teacher = teacher_detail.json()
            print(f"✅ Teacher view - Quiz: {quiz_teacher.get('title')}")
            
            # Show first question with correct answer
            if quiz_teacher.get('questions'):
                q = quiz_teacher['questions'][0]
                print(f"\n   Sample question (teacher view - correct answer visible):")
                print(f"   Q: {q.get('text')}")
                correct = next((a for a in q.get('answers', []) if a.get('is_correct')), None)
                print(f"   ✅ Correct answer: {correct.get('text') if correct else 'N/A'}")
        else:
            print(f"❌ Failed to fetch teacher view: {teacher_detail.text}")
    else:
        print("⚠️ No quiz found with 'HTML' in title, skipping teacher view test")
    
    # 6. Start a quiz attempt
    print("\n6️⃣ Starting quiz attempt...")
    if quiz_id:  # 👈 NOW THIS IS SAFE
        start_response = requests.post(
            f"{BASE_URL}/assessments/quizzes/{quiz_id}/start/",
            headers=headers
        )
        
        if start_response.status_code == 201:
            attempt = start_response.json()
            attempt_id = attempt.get('id')
            print(f"✅ Attempt started: #{attempt.get('attempt_number')}")
            print(f"   Attempt ID: {attempt_id}")
            
            # 7. Submit answers
            print("\n7️⃣ Submitting quiz answers...")
            
            # Get questions to answer
            quiz_detail = requests.get(
                f"{BASE_URL}/assessments/quizzes/{quiz_id}/",
                headers=headers
            ).json()
            
            responses = {}
            for q in quiz_detail.get('questions', [])[:3]:  # Only answer first 3 for test
                if q.get('question_type') == 'MCQ' and q.get('answers'):
                    # Choose first answer (may be wrong, but that's fine for test)
                    responses[str(q.get('id'))] = str(q['answers'][0].get('id'))
                elif q.get('question_type') == 'TF':
                    responses[str(q.get('id'))] = 'true'
            
            submit_response = requests.post(
                f"{BASE_URL}/assessments/quizzes/{quiz_id}/submit/",
                headers=headers,
                json={
                    "attempt_id": attempt_id,
                    "responses": responses
                }
            )
            
            if submit_response.status_code == 200:
                result = submit_response.json()
                print(f"✅ Quiz submitted!")
                print(f"   Score: {result.get('score_percentage'):.1f}%")
                print(f"   Passed: {result.get('passed')}")
            else:
                print(f"❌ Submit failed: {submit_response.text}")
        else:
            print(f"❌ Failed to start attempt: {start_response.text}")
    else:
        print("⚠️ No quiz found, skipping attempt test")
    
    # 8. Get student's attempt history
    print("\n8️⃣ Fetching attempt history...")
    attempts_response = requests.get(
        f"{BASE_URL}/assessments/quizzes/my_attempts/",
        headers=headers
    )
    
    if attempts_response.status_code == 200:
        attempts = attempts_response.json()
        print(f"✅ Found {len(attempts)} attempts")
        for attempt in attempts[:3]:  # Show first 3
            print(f"   - {attempt.get('quiz_title')}: {float(attempt.get('score_percentage', 0)):.1f}% "
                  f"({attempt.get('passed') and '✅' or '❌'})")
    else:
        print(f"❌ Failed to fetch attempts: {attempts_response.text}")
    
    # 9. Get quiz performance analytics (teacher)
    print("\n9️⃣ Fetching quiz performance analytics (teacher)...")
    # DEBUG: Print token info
    print(f"   Teacher token exists: {'Yes' if teacher_token else 'No'}")
    print(f"   Teacher token (first 20): {teacher_token[:20]}...")
    print(f"   Headers being sent: {{'Authorization': 'Bearer {teacher_token[:20]}...'}}")
    if quiz_id:  # 👈 NOW THIS IS SAFE
        performance_response = requests.get(
            f"{BASE_URL}/assessments/attempts/quiz_performance/?quiz_id={quiz_id}",
            headers=headers_teacher
        )
        
        if performance_response.status_code == 200:
            perf = performance_response.json()
            print(f"✅ Quiz Performance Analytics:")
            print(f"   Total Attempts: {perf.get('total_attempts')}")
            print(f"   Average Score: {perf.get('average_score'):.1f}%")
            print(f"   Pass Rate: {perf.get('pass_rate'):.1f}%")
            print(f"   Score Distribution:")
            for range_name, count in perf.get('score_distribution', {}).items():
                if count > 0:
                    print(f"      {range_name}: {count} students")
        else:
            print(f"❌ Failed to fetch performance: {performance_response.text}")
    else:
        print("⚠️ No quiz found, skipping performance analytics test")
    
    print("\n" + "=" * 60)
    print("✅ API TEST COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    test_quiz_api()