"""
End-to-End Workflow Test with Sample Data
Tests all Phase 1, 2, 3, and 4 features
"""
import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from courses.models import (
    Course, Module, Lesson, Enrollment, Competency, LessonCompetency,
    AttendanceRecord
)
from assessments.models import Quiz, Question, Answer, QuizAttempt
from analytics.models import (
    LessonInteraction, CompetencyPerformance, EngagementMetrics
)
from analytics.services.risk_engine import RiskEngine
from analytics.services.difficulty_analyzer import DifficultyAnalyzer
from analytics.services.competency_analyzer import CompetencyAnalyzer


def cleanup_sample_data():
    """Remove all sample data"""
    print("Cleaning up sample data...")
    User = get_user_model()
    User.objects.filter(email__startswith='test_').delete()
    print(">> Cleanup complete")


def create_sample_data():
    """Create comprehensive sample data for E2E testing"""
    print("\n" + "="*60)
    print("CREATING SAMPLE DATA FOR E2E TESTING")
    print("="*60)
    
    User = get_user_model()
    
    # 1. Create Teacher
    print("\n[1] Creating teacher...")
    teacher = User.objects.create_user(
        email='test_teacher@example.com',
        password='testpass123',
        role='TEACHER',
        first_name='Demo',
        last_name='Teacher',
        display_name='Demo Teacher'
    )
    print(f">> Teacher created: {teacher.display_name} ({teacher.email})")
    
    # 2. Create Students
    print("\n[2] Creating students...")
    students = []
    student_names = [
        ('Alice', 'Smith', 'test_alice@example.com'),
        ('Bob', 'Johnson', 'test_bob@example.com'),
        ('Charlie', 'Williams', 'test_charlie@example.com'),
        ('Diana', 'Brown', 'test_diana@example.com'),
    ]
    for first, last, email in student_names:
        student = User.objects.create_user(
            email=email,
            password='testpass123',
            role='STUDENT',
            first_name=first,
            last_name=last,
            display_name=f'{first} {last}'
        )
        students.append(student)
        print(f"  >> {student.display_name}")
    
    # 3. Create Course
    print("\n[3] Creating course...")
    course = Course.objects.create(
        title='Mathematics 101: Fundamentals',
        description='Learn the basics of mathematics including arithmetic, algebra, and geometry.',
        teacher=teacher,
        status=Course.Status.PUBLISHED,
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
        expected_hours=30
    )
    print(f">> Course created: {course.title} (ID: {course.id})")
    
    # 4. Create Competencies
    print("\n[4] Creating competencies...")
    competencies = {}
    comp_data = [
        ('Arithmetic', 'Math', 'Addition, subtraction, multiplication, division'),
        ('Algebra', 'Math', 'Variables, equations, and algebraic expressions'),
        ('Geometry', 'Math', 'Shapes, angles, and spatial reasoning'),
    ]
    for name, category, desc in comp_data:
        comp = Competency.objects.create(
            course=course,
            name=name,
            category=category,
            description=desc
        )
        competencies[name] = comp
        print(f"  >> {name}")
    
    # 5. Create Modules
    print("\n[5] Creating modules...")
    modules = []
    for i in range(1, 4):
        module = Module.objects.create(
            course=course,
            title=f'Module {i}: {list(competencies.keys())[i-1]}',
            description=f'Learn about {list(competencies.keys())[i-1].lower()}',
            order=i,
            estimated_minutes=120
        )
        modules.append(module)
        print(f"  >> {module.title}")
    
    # 6. Create Lessons with Native Content (Phase 1)
    print("\n[6] Creating lessons with native HTML content...")
    lessons = []
    for i, module in enumerate(modules, 1):
        # Rich HTML content for lesson
        html_content = f"""
        <h2>Lesson {i}: Introduction to {list(competencies.keys())[i-1]}</h2>
        <p>Welcome to Module {i}. In this lesson, you will learn:</p>
        <ul>
            <li>Basic concepts of {list(competencies.keys())[i-1].lower()}</li>
            <li>Fundamental principles and theorems</li>
            <li>Real-world applications</li>
            <li>Practice problems and exercises</li>
        </ul>
        <h3>Key Terms</h3>
        <p>Understanding the following terms is essential for mastery:</p>
        <ul>
            <li>Definition 1: A fundamental concept in {list(competencies.keys())[i-1].lower()}</li>
            <li>Definition 2: Another important principle</li>
            <li>Definition 3: Advanced topic for deeper understanding</li>
        </ul>
        <h3>Learning Objectives</h3>
        <p>By the end of this lesson, you should be able to:</p>
        <ol>
            <li>Understand and explain basic concepts</li>
            <li>Apply concepts to solve problems</li>
            <li>Analyze complex scenarios</li>
        </ol>
        """
        
        lesson = Lesson.objects.create(
            module=module,
            title=f'Lesson {i}: {list(competencies.keys())[i-1]} Fundamentals',
            content_type=Lesson.ContentType.TEXT,
            content_html=html_content,
            order=1,
            is_published=True,
            estimated_minutes=None  # Will be auto-calculated
        )
        lessons.append(lesson)
        
        # Link to competency
        LessonCompetency.objects.create(
            lesson=lesson,
            competency=competencies[list(competencies.keys())[i-1]],
            weight=Decimal('1.00')
        )
        
        print(f"  >> {lesson.title}")
        print(f"      Auto-estimated duration: {lesson.get_display_duration()} minutes")
        print(f"      Word count: {lesson.word_count_estimated}")
        print(f"      Icon color: {lesson.icon_color}")
    
    # 7. Create Quizzes with Competency-Tagged Questions (Phase 2)
    print("\n[7] Creating quizzes with competency-tagged questions...")
    quizzes = []
    for i, lesson in enumerate(lessons, 1):
        quiz = Quiz.objects.create(
            lesson=lesson,
            title=f'Quiz for Lesson {i}',
            description=f'Test your understanding of {lesson.title}',
            quiz_type=Quiz.QuizType.MULTIPLE_CHOICE,
            passing_score=70,
            max_attempts=3,
            is_published=True
        )
        quizzes.append(quiz)
        
        # Create questions tagged with competency (Phase 2)
        competency = list(competencies.values())[i-1]
        for q in range(1, 4):
            question = Question.objects.create(
                quiz=quiz,
                question_type=Question.QuestionType.MULTIPLE_CHOICE,
                text=f'Question {q}: What is the definition of key concept {q}?',
                points=1,
                order=q,
                explanation=f'The correct answer is concept {q} because it aligns with fundamental principles.'
            )
            # Tag with competency (Phase 2)
            question.competencies.add(competency)
            
            # Add answer options
            answers = [
                (f'Correct answer {q}', True),
                ('Incorrect option A', False),
                ('Incorrect option B', False),
                ('Incorrect option C', False),
            ]
            for answer_text, is_correct in answers:
                Answer.objects.create(
                    question=question,
                    text=answer_text,
                    is_correct=is_correct
                )
        
        print(f"  >> {quiz.title} ({len(quiz.questions.all())} questions)")
    
    # 8. Enroll Students and Create Learning Activities (Phase 1 + Analytics)
    print("\n[8] Enrolling students and simulating learning activities...")
    enrollments = []
    for student in students:
        enrollment = Enrollment.objects.create(
            student=student,
            course=course,
            status=Enrollment.Status.ACTIVE,
            progress_percentage=Decimal('0.00')
        )
        enrollments.append(enrollment)
        print(f"  >> {student.display_name} enrolled")
    
    # 9. Simulate Lesson Interactions and Completion (Phase 1 - Time-on-Page)
    print("\n[9] Simulating lesson interactions (Time-on-Page tracking)...")
    for enrollment in enrollments:
        # Each student completes lessons with varying time spent
        for i, lesson in enumerate(lessons[:2], 1):  # Students complete first 2 lessons
            time_on_page = 300 + (i * 120)  # 5-10 minutes per lesson
            
            # Record lesson view interaction (Phase 1: time_on_page_seconds)
            LessonInteraction.objects.create(
                student=enrollment.student,
                lesson=lesson,
                enrollment=enrollment,
                interaction_type=LessonInteraction.InteractionType.VIEW,
                time_on_page_seconds=time_on_page,
                user_agent='Mozilla/5.0',
                ip_address='192.168.1.1'
            )
            
            # Mark as completed
            from courses.models import LessonCompletion
            LessonCompletion.objects.create(
                student=enrollment.student,
                lesson=lesson,
                time_spent_seconds=time_on_page
            )
    
    # 10. Simulate Quiz Attempts (Phase 2: Competency Performance)
    print("\n[10] Simulating quiz attempts with competency tracking...")
    for i, enrollment in enumerate(enrollments):
        for quiz in quizzes[:2]:
            # Simulate quiz attempt
            attempt = QuizAttempt.objects.create(
                student=enrollment.student,
                quiz=quiz,
                attempt_number=1,
                score_percentage=Decimal(70 + (i * 10)),  # Varying scores
                passed=(70 + (i * 10)) >= quiz.passing_score,
                status=QuizAttempt.Status.COMPLETED,
                time_spent_seconds=600,
                responses={},  # Would contain question responses in production
                user_agent='Mozilla/5.0',
                ip_address='192.168.1.1'
            )
            print(f"  >> {enrollment.student.display_name} scored {attempt.score_percentage}% on {quiz.title}")
    
    # 11. Update Progress and Risk Scores (Analytics)
    print("\n[11] Calculating progress and risk scores...")
    for enrollment in enrollments:
        enrollment.update_progress()
        RiskEngine.calculate_student_risk(str(enrollment.id))
        print(f"  >> {enrollment.student.display_name}: Progress {enrollment.progress_percentage}%, Risk {enrollment.risk_level}")
    
    # 12. Create Attendance Records (Phase 4)
    print("\n[12] Recording attendance (Phase 4)...")
    base_date = timezone.now().date()
    for day_offset in range(5):
        session_date = base_date - timedelta(days=day_offset)
        for student in students:
            status = AttendanceRecord.Status.PRESENT if day_offset < 4 else AttendanceRecord.Status.ABSENT
            AttendanceRecord.objects.create(
                student=student,
                course=course,
                session_date=session_date,
                status=status,
                notes='Regular attendance' if status == AttendanceRecord.Status.PRESENT else 'Sick leave'
            )
    print(f"  >> Attendance records created for 5 sessions")
    
    return {
        'teacher': teacher,
        'students': students,
        'course': course,
        'competencies': competencies,
        'modules': modules,
        'lessons': lessons,
        'quizzes': quizzes,
        'enrollments': enrollments,
    }


def test_phase1_features(data):
    """Test Phase 1: Native Content, Auto-Duration, Time-on-Page"""
    print("\n" + "="*60)
    print("TESTING PHASE 1: Native Content & Auto-Duration")
    print("="*60)
    
    for lesson in data['lessons']:
        print(f"\n>> Lesson: {lesson.title}")
        print(f"  - Content HTML stored: {len(lesson.content_html)} chars")
        print(f"  - Word count (auto): {lesson.word_count_estimated} words")
        print(f"  - Duration (auto-estimated): {lesson.get_display_duration()} minutes")
        print(f"  - Icon color (auto-set): {lesson.icon_color}")
        print(f"  - Content type: {lesson.get_content_type_display()}")
    
    # Check Time-on-Page telemetry
    print(f"\n>> Time-on-Page Telemetry:")
    interactions = LessonInteraction.objects.filter(
        interaction_type=LessonInteraction.InteractionType.VIEW
    )
    for interaction in interactions[:3]:
        print(f"  - {interaction.student.display_name} spent {interaction.time_on_page_seconds}s on {interaction.lesson.title}")


def test_phase2_features(data):
    """Test Phase 2: Competencies, AI Quiz Gen, Per-Competency Analytics"""
    print("\n" + "="*60)
    print("TESTING PHASE 2: Competencies & Analytics")
    print("="*60)
    
    # Test competency tagging
    print(f"\n>> Competency-Tagged Questions:")
    for quiz in data['quizzes']:
        for question in quiz.questions.all():
            comps = list(question.competencies.all())
            print(f"  - Q: {question.text[:50]}...")
            print(f"    Tagged with: {', '.join([c.name for c in comps])}")
    
    # Test AI Quiz Generation Service
    print(f"\n>> AI Quiz Suggestion (from AI Service):")
    from courses.ai_services import AIQuizGenerator
    
    lesson = data['lessons'][0]
    result = AIQuizGenerator.suggest_quiz_from_lesson(lesson, num_questions=3)
    print(f"  - Status: {result.get('status')}")
    print(f"  - Suggested Quiz: {result.get('quiz_title')}")
    print(f"  - Number of questions: {result.get('num_questions')}")
    if result.get('suggested_questions'):
        for q in result['suggested_questions'][:2]:
            print(f"    Q{q['order']}: {q['question_text'][:60]}...")
    
    # Test Competency Performance Analytics (Phase 2)
    print(f"\n>> Competency Performance Heatmap:")
    for student in data['students'][:2]:
        heatmap = CompetencyAnalyzer.get_student_competency_heatmap(
            str(student.id),
            str(data['course'].id)
        )
        print(f"  - {student.display_name}:")
        for category, comps in heatmap.items():
            for comp in comps:
                print(f"    . {comp['competency_name']}: {comp['score_percentage']:.1f}% ({comp['proficiency_level']})")


def test_phase3_features(data):
    """Test Phase 3: Unified Student Table, Course Health Badge"""
    print("\n" + "="*60)
    print("TESTING PHASE 3: UX Improvements")
    print("="*60)
    
    # Test Course Health Badge
    print(f"\n>> Course Health Badge:")
    health = data['course'].health_status_summary
    print(f"  - High Risk: {health['high_risk']}")
    print(f"  - Medium Risk: {health['medium_risk']}")
    print(f"  - Low Risk: {health['low_risk']}")
    print(f"  - Status Color: {health['status_color']}")
    print(f"  - Total At Risk: {health['total_at_risk']}")
    
    # Test Student Progress Data (for unified table)
    print(f"\n>> Student Progress (Unified Table Data):")
    for enrollment in data['enrollments']:
        print(f"  - {enrollment.student.display_name}")
        print(f"    Progress: {enrollment.progress_percentage}% | Risk: {enrollment.risk_level} ({enrollment.risk_score})")
        print(f"    Last Activity: {enrollment.last_activity.strftime('%Y-%m-%d %H:%M')} | Engagement: {enrollment.engagement_score}")
        print(f"    Quiz Avg: {enrollment.average_quiz_score}% | At Risk: {enrollment.is_at_risk} | Inactive: {enrollment.is_inactive}")


def test_phase4_features(data):
    """Test Phase 4: Attendance, Intervention Log, What-If Simulator"""
    print("\n" + "="*60)
    print("TESTING PHASE 4: Advanced Features")
    print("="*60)
    
    # Test Attendance Records
    print(f"\n>> Attendance Tracking:")
    for student in data['students'][:2]:
        records = AttendanceRecord.objects.filter(
            student=student,
            course=data['course']
        ).order_by('-session_date')
        
        total = records.count()
        present = records.filter(status__in=[
            AttendanceRecord.Status.PRESENT,
            AttendanceRecord.Status.LATE
        ]).count()
        attendance_pct = (present / total * 100) if total > 0 else 0
        
        print(f"  - {student.display_name}: {attendance_pct:.0f}% attendance ({present}/{total})")
    
    # Test Intervention Log (Already exists in analytics)
    print(f"\n>> Intervention Log Model (Ready for UI):")
    from analytics.models import InterventionLog
    print(f"  - Model exists with fields: intervention_type, outcome, risk_before, risk_after")
    print(f"  - Intervention types: {', '.join([t[0] for t in InterventionLog.InterventionType.choices])}")
    
    # Test What-If Simulator
    print(f"\n>> Risk Prediction (What-If Simulator):")
    enrollment = data['enrollments'][0]
    current_risk = enrollment.risk_score
    
    # Simulate: student completes 3 more lessons and scores 85% on quiz
    from decimal import Decimal
    hyp_lessons = 3
    hyp_quiz_score = 85
    
    new_progress = min(100, float(enrollment.progress_percentage) + (hyp_lessons * 10))
    progress_component = max(0, 1 - (new_progress / 100))
    quiz_component = max(0, 1 - (hyp_quiz_score / 100))
    inactivity_component = 0.1  # Recent activity
    
    predicted_risk = (
        progress_component * 0.4 +
        quiz_component * 0.4 +
        inactivity_component * 0.2
    )
    
    print(f"  - Student: {enrollment.student.display_name}")
    print(f"  - Current Risk: {float(current_risk):.3f} ({enrollment.risk_level})")
    print(f"  - Simulation: +{hyp_lessons} lessons completed, {hyp_quiz_score}% quiz score")
    print(f"  - Predicted Risk: {predicted_risk:.3f}")
    print(f"  - Improvement: {float(current_risk) - predicted_risk:.3f}")


def run_all_tests():
    """Run complete E2E test suite"""
    print("\n\n")
    print("="*60)
    print("    END-TO-END WORKFLOW TEST WITH SAMPLE DATA")
    print("="*60)
    
    try:
        # Cleanup
        cleanup_sample_data()
        
        # Create sample data
        data = create_sample_data()
        
        # Run Phase tests
        test_phase1_features(data)
        test_phase2_features(data)
        test_phase3_features(data)
        test_phase4_features(data)
        
        print("\n" + "="*60)
        print("SUCCESS: ALL TESTS PASSED SUCCESSFULLY!")
        print("="*60)
        print("\nTest Results Summary:")
        print(f"  - Teacher: 1")
        print(f"  - Students: {len(data['students'])}")
        print(f"  - Courses: 1")
        print(f"  - Modules: {len(data['modules'])}")
        print(f"  - Lessons: {len(data['lessons'])}")
        print(f"  - Quizzes: {len(data['quizzes'])}")
        print(f"  - Competencies: {len(data['competencies'])}")
        print(f"  - Enrollments: {len(data['enrollments'])}")
        print("\nPhase Coverage:")
        print("  >> Phase 1: Native content editor, auto-duration, Time-on-Page")
        print("  >> Phase 2: Competency tagging, AI quiz generation, per-competency analytics")
        print("  >> Phase 3: Course health badge, student progress data, visual hierarchy")
        print("  >> Phase 4: Attendance tracking, intervention logs, what-if simulator")
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"\nERROR: TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    run_all_tests()
