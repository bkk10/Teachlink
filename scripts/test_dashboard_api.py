"""
Test script to verify the student dashboard API is working.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()

def test_student_api():
    client = Client()
    
    # Get a student user
    student = User.objects.filter(role='STUDENT').first()
    if not student:
        print("❌ No student user found")
        return
    
    print(f"Testing API for student: {student.display_name}")
    
    # Login
    client.force_login(student)
    
    # Test the API
    response = client.get('/dashboard/api/student/')
    print(f"\nStatus code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ API returned data successfully")
        print(f"   Student name: {data.get('student_name')}")
        print(f"   Overall progress: {data.get('overall_progress')}")
        print(f"   Courses count: {len(data.get('courses', []))}")
        print(f"   Recent attempts: {len(data.get('recent_quiz_attempts', []))}")
    else:
        print(f"❌ API failed: {response.content[:500]}")

if __name__ == '__main__':
    test_student_api()
