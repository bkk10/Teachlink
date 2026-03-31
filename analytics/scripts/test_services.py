# filepath: /analytics/scripts/test_services.py
"""
Quick test script for analytics services
Run with: python manage.py shell < analytics/scripts/test_services.py
"""

from analytics.services.risk_engine import RiskEngine
from analytics.services.difficulty_analyzer import DifficultyAnalyzer
from analytics.services.alert_generator import AlertGenerator
from django.contrib.auth import get_user_model
from courses.models import Course, Enrollment
from assessments.models import Quiz
import datetime

User = get_user_model()

def test_risk_engine():
    """Test if risk engine can calculate risk scores"""
    print("\n🔍 Testing Risk Engine...")
    
    # Get first student (or create one if none exists)
    student = User.objects.filter(role='STUDENT').first()
    if not student:
        print("❌ No student found. Create a student first.")
        return
    
    # Get first course
    course = Course.objects.first()
    if not course:
        print("❌ No course found. Create a course first.")
        return
    
    # Calculate risk
    risk_score = RiskEngine.calculate_student_risk(student.id, course.id)
    print(f"✅ Risk score for {student.email}: {risk_score}")
    
    # Get risk factors
    factors = RiskEngine.get_risk_factors(student.id, course.id)
    print(f"📊 Risk factors: {factors}")
    
    return risk_score

def test_alert_generation():
    """Test if alerts are being generated"""
    print("\n🔍 Testing Alert Generator...")
    
    from analytics.models import Alert
    
    # Get recent alerts
    recent_alerts = Alert.objects.filter(is_resolved=False)[:5]
    print(f"📢 Unresolved alerts: {recent_alerts.count()}")
    
    for alert in recent_alerts:
        print(f"  - {alert.alert_type}: {alert.message} (Severity: {alert.severity})")
    
    return recent_alerts.count()

def test_difficulty_analyzer():
    """Test difficulty analysis"""
    print("\n🔍 Testing Difficulty Analyzer...")
    
    # Get first quiz
    quiz = Quiz.objects.first()
    if not quiz:
        print("❌ No quiz found. Create a quiz first.")
        return
    
    # Analyze difficulty
    difficulty = DifficultyAnalyzer.analyze_quiz_difficulty(quiz.id)
    print(f"📈 Quiz '{quiz.title}' difficulty: {difficulty}")
    
    return difficulty

if __name__ == "__main__":
    print("="*50)
    print("ANALYTICS SERVICES TEST")
    print("="*50)
    
    test_risk_engine()
    test_alert_generation()
    test_difficulty_analyzer()
    
    print("\n✅ Tests complete!")