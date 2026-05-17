#!/usr/bin/env python
"""
Test dashboard functionality
Run: python manage.py shell < scripts/test_dashboard.py
"""
import django
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from courses.models import Enrollment
from analytics.models import Alert
from django.utils import timezone
from django.urls import resolve, Resolver404
import requests
from django.conf import settings

User = get_user_model()

def test_dashboard():
    print("=" * 60)
    print("🧪 TESTING DASHBOARD")
    print("=" * 60)
    
    # 1. Check teacher dashboard access
    print("\n1️⃣ Checking teacher dashboard...")
    
    # Try to find Mr. Ochieng specifically
    teacher = User.objects.filter(email='mr_ochieng@teachly.com').first()
    
    # Fallback to any teacher
    if not teacher:
        teacher = User.objects.filter(role='TEACHER').first()
    
    if teacher:
        print(f"   ✅ Teacher found: {teacher.display_name}")  # type: ignore
        
        # Check teacher's courses
        from courses.models import Course
        courses = Course.objects.filter(teacher=teacher)
        print(f"   📚 Courses: {courses.count()}")
        
        # Check enrollments in teacher's courses
        enrollments = Enrollment.objects.filter(course__teacher=teacher)
        print(f"   👥 Students: {enrollments.count()}")
        
        # Check risk distribution
        risk_counts = {
            'HIGH': enrollments.filter(risk_level='HIGH').count(),
            'MEDIUM': enrollments.filter(risk_level='MEDIUM').count(),
            'LOW': enrollments.filter(risk_level='LOW').count(),
        }
        print(f"   📊 Risk: High={risk_counts['HIGH']}, "
              f"Medium={risk_counts['MEDIUM']}, "
              f"Low={risk_counts['LOW']}")
        
        # Check alerts
        alerts = Alert.objects.filter(teacher=teacher, status='ACTIVE')
        print(f"   🔔 Active Alerts: {alerts.count()}")
    else:
        print("   ❌ No teacher found")
    
    # 2. Check student dashboard access
    print("\n2️⃣ Checking student dashboard...")
    student = User.objects.filter(role='STUDENT').first()
    if student:
        print(f"   ✅ Student found: {student.display_name}")  # type: ignore
        
        # Check student's enrollments
        enrollments = Enrollment.objects.filter(student=student, status='ACTIVE')
        print(f"   📚 Enrolled courses: {enrollments.count()}")
        
        for enrollment in enrollments:
            print(f"      • {enrollment.course.title}: "
                  f"Progress {enrollment.progress_percentage}%, "
                  f"Risk {enrollment.risk_level}")
    else:
        print("   ❌ No student found")
    
    # 3. Check URL routing
    print("\n3️⃣ Checking URL routing...")
    url_patterns = [
        ('teacher_dashboard', 'Teacher Dashboard View', '/dashboard/teacher/'),
        ('student_dashboard', 'Student Dashboard View', '/dashboard/student/'),
        ('alerts_center', 'Alerts Center View', '/dashboard/alerts/'),
        ('teacher_api', 'Teacher Dashboard API', '/dashboard/api/teacher/'),
        ('student_api', 'Student Dashboard API', '/dashboard/api/student/'),
        ('risk_data_api', 'Risk Data API', '/dashboard/api/risk-data/'),
        ('alerts_api', 'Alerts API', '/dashboard/api/alerts/'),
        ('difficulty_api', 'Difficulty API', '/dashboard/api/difficulty/'),
    ]

    from django.urls import reverse
    for url_name, description, expected_path in url_patterns:
        try:
            url = reverse(url_name)
            status = "✅" if url == expected_path else "⚠️"
            print(f"   {status} {description}: {url} (expected: {expected_path})")
        except Exception as e:
            print(f"   ❌ {description}: not configured ({str(e)})")

    # 4. Quick API check (optional, requires server)
    print("\n4️⃣ Quick API check (server must be running)...")
    base_url = 'http://127.0.0.1:8000'

    try:
        # Login request
        login_data = {
            'email': 'mr_ochieng@teachly.com',
            'password': 'Teacher123!'
        }
        
        print(f"   Logging in as {login_data['email']}...")
        login_response = requests.post(f'{base_url}/api/auth/login/', json=login_data, allow_redirects=False)
        
        if login_response.status_code == 200:
            token = login_response.json().get('access')
            print(f"   ✅ Login successful, token received")
            print(f"   Token (first 20 chars): {token[:20]}...")
            
            headers = {'Authorization': f'Bearer {token}'}
            print(f"   Headers being sent: {headers}")
            
            # Test teacher dashboard API
            api_url = f'{base_url}/dashboard/api/teacher/'
            print(f"   Testing API: {api_url}")
            api_response = requests.get(api_url, headers=headers, allow_redirects=False)
            
            if api_response.status_code == 200:
                print(f"   ✅ Teacher Dashboard API: 200 OK")
                data = api_response.json()
                print(f"      • Total Students: {data['kpi']['total_students']}")
                print(f"      • Active Alerts: {data['kpi']['active_alerts']}")
            else:
                print(f"   ❌ Teacher Dashboard API: {api_response.status_code}")
                print(f"      Response: {api_response.text}")
                
                # Try with different header format
                print(f"\n   🔍 Trying alternative header format...")
                headers2 = {'Authorization': f'Token {token}'}
                api_response2 = requests.get(api_url, headers=headers2, allow_redirects=False)
                print(f"   Result with 'Token' prefix: {api_response2.status_code}")
                
                # Try with session authentication
                session = requests.Session()
                session.headers.update({'Authorization': f'Bearer {token}'})
                session.get(f'{base_url}/api/auth/login/', json=login_data)  # This might set cookies
                api_response3 = session.get(api_url, allow_redirects=False)
                print(f"   Result with session: {api_response3.status_code}")
        else:
            print(f"   ⚠️  Login failed: {login_response.status_code}")
            print(f"      Response: {login_response.text[:200]}")
    except requests.exceptions.ConnectionError:
        print(f"   ⚠️  Server not running - API check skipped")
    except Exception as e:
        print(f"   ⚠️  API check error: {e}")


if __name__ == "__main__":
    test_dashboard()