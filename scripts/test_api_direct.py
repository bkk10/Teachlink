"""
Test the StudentDashboardAPI directly to see what's happening.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from dashboard.views import StudentDashboardAPI
from django.http import HttpRequest
from django.contrib.auth import get_user_model

User = get_user_model()

def test_api_directly():
    # Get a student user
    student = User.objects.filter(role='STUDENT').first()
    if not student:
        print("❌ No student found")
        return
    
    print(f"Testing API for: {student.display_name} ({student.email})")
    print(f"Role: {student.role}")
    print(f"Is authenticated: {student.is_authenticated}")
    
    # Create a mock request
    class MockRequest:
        def __init__(self, user):
            self.user = user
            
    request = MockRequest(student)
    
    # Call the API directly
    api = StudentDashboardAPI()
    try:
        response = api.get(request)
        print(f"\n✅ API returned status: {response.status_code}")
        data = response.data
        print(f"Student name in response: {data.get('student_name')}")
        print(f"Overall progress: {data.get('overall_progress')}")
        print(f"Courses: {len(data.get('courses', []))}")
        print(f"Recent attempts: {len(data.get('recent_quiz_attempts', []))}")
    except Exception as e:
        print(f"\n❌ API error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_api_directly()
