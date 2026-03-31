#!/usr/bin/env python
"""
Test script for Course API endpoints
"""
import requests
import json
from pprint import pprint

BASE_URL = "http://localhost:8000/api"

def test_course_api():
    print("🔍 TESTING COURSE API ENDPOINTS")
    print("=" * 60)
    
    # 1. Login as teacher
    print("\n1️⃣ Logging in as teacher...")
    login_response = requests.post(
        f"{BASE_URL}/auth/login/",
        json={
            "email": "mr_ochieng@teachlink.com",
            "password": "Teacher123!"
        }
    )
    
    if login_response.status_code == 200:
        teacher_token = login_response.json()['access']
        print(f"✅ Teacher login successful")
        print(f"   Token (first 20 chars): {teacher_token[:20]}...")
    else:
        print(f"❌ Teacher login failed: {login_response.text}")
        return
    
    # 2. Get teacher's courses
    print("\n2️⃣ Fetching teacher's courses...")
    headers = {
        "Authorization": f"Bearer {teacher_token}",
        "Content-Type": "application/json"
    }
    
    courses_response = requests.get(
        f"{BASE_URL}/courses/courses/",
        headers=headers
    )
    
    print(f"   Status Code: {courses_response.status_code}")
    
    if courses_response.status_code == 200:
        courses = courses_response.json()
        print(f"✅ Found {len(courses)} courses")
        
        # Store course IDs for later use
        course_ids = {}
        for course in courses:
            print(f"   - {course.get('title', 'No title')} (ID: {course.get('id', 'No ID')})")
            course_ids[course['title']] = course['id']
    else:
        print(f"❌ Failed to fetch courses: {courses_response.text}")
        return
    
    # 3. Login as student (James)
    print("\n3️⃣ Logging in as student (James)...")
    student_login = requests.post(
        f"{BASE_URL}/auth/login/",
        json={
            "email": "james.kamau@student.com",
            "password": "Student123!"
        }
    )
    
    if student_login.status_code == 200:
        student_token = student_login.json()['access']
        print("✅ Student login successful")
    else:
        print(f"❌ Student login failed: {student_login.text}")
        return
    
    # 4. Get available courses as student
    print("\n4️⃣ Fetching available courses for student...")
    headers = {"Authorization": f"Bearer {student_token}"}
    available_response = requests.get(
        f"{BASE_URL}/courses/courses/",
        headers=headers
    )
    
    if available_response.status_code == 200:
        available = available_response.json()
        print(f"✅ Found {len(available)} available courses")
        for course in available:
            print(f"   - {course.get('title', 'No title')}")
    else:
        print(f"❌ Failed to fetch available courses: {available_response.text}")
    
    # 5. Enroll in Web Development course
    print("\n5️⃣ Enrolling in Web Development course...")
    web_dev_course_id = course_ids.get('Introduction to Web Development')
    
    if web_dev_course_id:
        print(f"   Course ID: {web_dev_course_id}")
        enroll_response = requests.post(
            f"{BASE_URL}/courses/courses/{web_dev_course_id}/enroll/",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        if enroll_response.status_code in [200, 201]:
            print("✅ Successfully enrolled in course")
            pprint(enroll_response.json())
        else:
            print(f"❌ Enrollment failed: {enroll_response.text}")
    else:
        print("❌ Web Development course not found")
    
    # 6. Get course details with enrollment status
    print("\n6️⃣ Fetching course details with enrollment status...")
    if web_dev_course_id:
        detail_response = requests.get(
            f"{BASE_URL}/courses/courses/{web_dev_course_id}/",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        if detail_response.status_code == 200:
            details = detail_response.json()
            print("✅ Course details retrieved")
            print(f"   Enrollment status: {details.get('enrollment_status', 'N/A')}")
            print(f"   Your progress: {details.get('student_progress', {}).get('progress', 'N/A')}%")
        else:
            print(f"❌ Failed to fetch course details: {detail_response.text}")
    else:
        print("❌ No course ID available for details")
    
    # 7. Login as at-risk student (Peter)
    print("\n7️⃣ Logging in as at-risk student (Peter)...")
    peter_login = requests.post(
        f"{BASE_URL}/auth/login/",
        json={
            "email": "peter.odhiambo@student.com",
            "password": "Student123!"
        }
    )
    
    if peter_login.status_code == 200:
        peter_token = peter_login.json()['access']
        print("✅ Peter login successful")
        
        # Get Peter's enrollments
        headers = {"Authorization": f"Bearer {peter_token}"}
        enrollments_response = requests.get(
            f"{BASE_URL}/courses/enrollments/my_enrollments/",
            headers=headers
        )
        
        if enrollments_response.status_code == 200:
            enrollments = enrollments_response.json()
            print(f"✅ Found {len(enrollments)} enrollments for Peter")
            for enrollment in enrollments:
                print(f"   - Course: {enrollment.get('course_title', 'N/A')}")
                print(f"     Risk Level: {enrollment.get('risk_level', 'N/A')}")
                print(f"     Progress: {enrollment.get('progress_percentage', 'N/A')}%")
                print(f"     Last Active: {enrollment.get('last_activity', 'N/A')}")
        else:
            print(f"❌ Failed to fetch enrollments: {enrollments_response.text}")
    else:
        print(f"❌ Peter login failed: {peter_login.text}")
    
    print("\n" + "=" * 60)
    print("✅ API TESTING COMPLETED")

if __name__ == "__main__":
    test_course_api()