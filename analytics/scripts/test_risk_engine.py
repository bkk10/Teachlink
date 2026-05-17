#!/usr/bin/env python
"""
Test the Risk Engine with our existing test data
Run: python manage.py shell < scripts/test_risk_engine.py
"""
import django
import os
import sys
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings.development')
django.setup()

from courses.models import Enrollment
from analytics.services.risk_engine import RiskEngine
from analytics.services.difficulty_analyzer import DifficultyAnalyzer
from analytics.services.alert_generator import AlertGenerator
from analytics.models import RiskHistory, LessonDifficulty, Alert
from django.utils import timezone

def test_risk_engine():
    print("=" * 60)
    print("🧪 TESTING RISK ENGINE")
    print("=" * 60)
    
    # 1. Get all active enrollments
    enrollments = Enrollment.objects.filter(status='ACTIVE')
    print(f"\n📊 Found {enrollments.count()} active enrollments")
    
    # 2. Calculate risk for each enrollment
    print("\n🔍 Calculating risk scores...")
    results = []
    for enrollment in enrollments:
        result = RiskEngine.calculate_student_risk(enrollment.id)
        if result:
            results.append(result)
            print(f"\n   Student: {result['student_name']}")
            print(f"   Risk Score: {result['risk_score']} ({result['risk_level']})")
            print(f"   Performance: {result['components']['performance']}")
            print(f"   Progress: {result['components']['progress']}")
            print(f"   Engagement: {result['components']['engagement']}")
            
            if result['contributing_factors']:
                print(f"   ⚠️  Factors: {[f['factor'] for f in result['contributing_factors']]}")
    
        # 3. Check Peter (should be HIGH risk)
    print("\n" + "-" * 40)
    print("🔬 VERIFYING HIGH-RISK STUDENT (Peter Odhiambo)")
    peter = Enrollment.objects.filter(
        student__display_name='Peter Odhiambo',  # type: ignore
        status='ACTIVE'
    ).first()

    if peter:
        peter_result = RiskEngine.calculate_student_risk(str(peter.id))
        if peter_result:
            print(f"   Risk Level: {peter_result['risk_level']}")
            print(f"   Risk Score: {peter_result['risk_score']}")
            print(f"   Days Inactive: {peter.days_since_last_activity}")
            print(f"   Progress: {peter.progress_percentage}%")
            print(f"   Expected: HIGH risk (≥50%)")  # Updated threshold
            print(f"   ✅ PASSED" if peter_result['risk_score'] >= 50 else "❌ FAILED")

    # 4. Check James (should be LOW risk)
    print("\n" + "-" * 40)
    print("🔬 VERIFYING LOW-RISK STUDENT (James Kamau)")
    james = Enrollment.objects.filter(
        student__display_name='James Kamau',  # type: ignore
        status='ACTIVE'
    ).first()

    if james:
        james_result = RiskEngine.calculate_student_risk(str(james.id))
        if james_result:
            print(f"   Risk Level: {james_result['risk_level']}")
            print(f"   Risk Score: {james_result['risk_score']}")
            print(f"   Progress: {james.progress_percentage}%")
            print(f"   Expected: LOW risk (<30%)")  # Updated threshold
            print(f"   ✅ PASSED" if james_result['risk_score'] < 30 else "❌ FAILED")

    # 5. Check Sarah (should be MEDIUM risk)
    print("\n" + "-" * 40)
    print("🔬 VERIFYING MEDIUM-RISK STUDENT (Sarah Akinyi)")
    sarah = Enrollment.objects.filter(
        student__display_name='Sarah Akinyi',  # type: ignore
        status='ACTIVE'
    ).first()

    if sarah:
        sarah_result = RiskEngine.calculate_student_risk(str(sarah.id))
        if sarah_result:
            print(f"   Risk Level: {sarah_result['risk_level']}")
            print(f"   Risk Score: {sarah_result['risk_score']}")
            print(f"   Expected: MEDIUM risk (30-50%)")  # Updated threshold
            is_medium = 30 <= sarah_result['risk_score'] < 50
            print(f"   ✅ PASSED" if is_medium else "❌ FAILED")
            # 6. Test difficulty analyzer
    print("\n" + "-" * 40)
    print("📊 TESTING DIFFICULTY ANALYZER")

    from courses.models import Lesson
    lesson = Lesson.objects.filter(quiz__isnull=False).first()
    if lesson:
        difficulty = DifficultyAnalyzer.analyze_lesson_difficulty(str(lesson.id))
        if difficulty:
            print(f"   Lesson: {difficulty['lesson_title']}")
            print(f"   Difficulty Score: {difficulty['difficulty_score'] * 100:.1f}%")  # Convert to %
            print(f"   Difficulty Level: {difficulty['difficulty_level']}")
            print(f"   Components:")
            print(f"      Failure Rate: {difficulty['components']['failure_rate'] * 100:.1f}%")
            print(f"      Attempt Intensity: {difficulty['components']['attempt_intensity'] * 100:.1f}%")
            print(f"      Access Frequency: {difficulty['components']['access_frequency'] * 100:.1f}%")
        
    # 7. Test alert generation
    print("\n" + "-" * 40)
    print("🚨 TESTING ALERT GENERATOR")
    
    alerts = AlertGenerator.check_and_generate_alerts()
    print(f"   Generated {len(alerts)} new alerts")
    
    # Show active alerts
    active = AlertGenerator.get_active_alerts()
    print(f"\n   Active Alerts: {active.count()}")
    for alert in active[:5]:  # Show first 5
        print(f"      • {alert.student.display_name}: {alert.title}")
        print(f"        Severity: {alert.severity}, Status: {alert.status}")
    
    # 8. Show risk history for Peter
    print("\n" + "-" * 40)
    print("📈 RISK HISTORY TREND")
    
    if peter:
        trend = RiskEngine.get_risk_trend(
            student_id=peter.student.id,
            course_id=peter.course.id,
            days=7
        )
        print(f"   Peter Odhiambo - Risk Trend:")
        for entry in trend[-3:]:  # Last 3 entries
            print(f"      {entry['date']}: {entry['risk_score']:.3f} ({entry['risk_level']})")
    
    print("\n" + "=" * 60)
    print("✅ RISK ENGINE TEST COMPLETE")
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    results = test_risk_engine()
    
    # Summary
    if results:
        risk_levels = {}
        for r in results:
            level = r['risk_level']
            risk_levels[level] = risk_levels.get(level, 0) + 1
        
        print("\n📊 RISK DISTRIBUTION SUMMARY:")
        for level, count in risk_levels.items():
            print(f"   {level}: {count} students")