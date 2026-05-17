#!/usr/bin/env python
"""
Seed script for course test data
Run: python manage.py shell < scripts/seed_courses.py
"""
import django
import random
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
# from assessments.models import Quiz, Question, Answer
import uuid

User = get_user_model()

def create_test_data():
    print("🌱 Seeding test data for Teachly...")
    print("=" * 50)
    
    # ============================================
    # 1. CREATE TEACHER
    # ============================================
    teacher_email = "mr_ochieng@teachly.com"
    teacher, created = User.objects.get_or_create(
        email=teacher_email,
        defaults={
            'username': 'mr_ochieng',
            'display_name': 'Mr. Ochieng',
            'role': 'TEACHER',
            'is_active': True,
            'email_verified': True
        }
    )
    
    if created:
        teacher.set_password('Teacher123!')
        teacher.save()
        print(f"✅ Created teacher: {teacher.display_name}")
    else:
        print(f"✅ Found existing teacher: {teacher.display_name}")
    
    # ============================================
    # 2. CREATE STUDENTS
    # ============================================
    students_data = [
        {
            'email': 'james.kamau@student.com',
            'username': 'james_kamau',
            'display_name': 'James Kamau',
            'role': 'STUDENT'
        },
        {
            'email': 'sarah.akinyi@student.com',
            'username': 'sarah_akinyi',
            'display_name': 'Sarah Akinyi',
            'role': 'STUDENT'
        },
        {
            'email': 'peter.odhiambo@student.com',
            'username': 'peter_odhiambo',
            'display_name': 'Peter Odhiambo',
            'role': 'STUDENT'
        },
        {
            'email': 'mary.wanjiku@student.com',
            'username': 'mary_wanjiku',
            'display_name': 'Mary Wanjiku',
            'role': 'STUDENT'
        },
        {
            'email': 'david.mutua@student.com',
            'username': 'david_mutua',
            'display_name': 'David Mutua',
            'role': 'STUDENT'
        }
    ]
    
    students = []
    for student_data in students_data:
        student, created = User.objects.get_or_create(
            email=student_data['email'],
            defaults=student_data
        )
        if created:
            student.set_password('Student123!')
            student.save()
            print(f"✅ Created student: {student.display_name}")
        else:
            print(f"✅ Found existing student: {student.display_name}")
        students.append(student)
    
    # ============================================
    # 3. CREATE COURSES
    # ============================================
    courses_data = [
        {
            'title': 'Introduction to Web Development',
            'description': 'Learn HTML, CSS, and JavaScript fundamentals. Build your first website!',
            'status': Course.Status.PUBLISHED,
            'start_date': timezone.now().date(),
            'end_date': timezone.now().date() + timedelta(days=90),
            'expected_hours': 60
        },
        {
            'title': 'Data Science with Python',
            'description': 'Master data analysis, visualization, and machine learning basics with Python.',
            'status': Course.Status.PUBLISHED,
            'start_date': timezone.now().date() - timedelta(days=30),
            'end_date': timezone.now().date() + timedelta(days=60),
            'expected_hours': 80
        },
        {
            'title': 'Mobile App Development with Flutter',
            'description': 'Build cross-platform mobile apps for iOS and Android.',
            'status': Course.Status.DRAFT,
            'start_date': timezone.now().date() + timedelta(days=15),
            'end_date': timezone.now().date() + timedelta(days=105),
            'expected_hours': 70
        }
    ]
    
    courses = []
    for course_data in courses_data:
        course, created = Course.objects.get_or_create(
            title=course_data['title'],
            teacher=teacher,
            defaults=course_data
        )
        if created:
            print(f"✅ Created course: {course.title}")
        else:
            print(f"✅ Found existing course: {course.title}")
        courses.append(course)
    
    # ============================================
    # 4. CREATE MODULES AND LESSONS
    # ============================================
    
    # Web Development Course Modules
    web_course = courses[0]
    
    modules_data = [
        {
            'course': web_course,
            'title': 'HTML Fundamentals',
            'description': 'Learn the structure of web pages',
            'order': 1,
            'estimated_minutes': 120
        },
        {
            'course': web_course,
            'title': 'CSS Styling',
            'description': 'Make your websites beautiful',
            'order': 2,
            'estimated_minutes': 180
        },
        {
            'course': web_course,
            'title': 'JavaScript Basics',
            'description': 'Add interactivity to your sites',
            'order': 3,
            'estimated_minutes': 240
        },
        {
            'course': web_course,
            'title': 'Responsive Design',
            'description': 'Websites that work on all devices',
            'order': 4,
            'estimated_minutes': 150
        }
    ]
    
    for module_data in modules_data:
        module, created = Module.objects.get_or_create(
            course=module_data['course'],
            title=module_data['title'],
            defaults={
                'description': module_data['description'],
                'order': module_data['order'],
                'estimated_minutes': module_data['estimated_minutes']
            }
        )
        
        if created:
            print(f"  📚 Created module: {module.title}")
            
            # Create lessons for each module
            if module.title == 'HTML Fundamentals':
                lessons = [
                    {
                        'title': 'Introduction to HTML',
                        'content_type': 'VIDEO',
                        'video_url': 'https://www.youtube.com/watch?v=UB1O30fR-EE',
                        'order': 1,
                        'estimated_minutes': 10,
                        'is_published': True
                    },
                    {
                        'title': 'HTML Elements and Tags',
                        'content_type': 'TEXT',
                        'content_text': 'HTML uses tags like <h1>, <p>, <div> to structure content...',
                        'order': 2,
                        'estimated_minutes': 15,
                        'is_published': True
                    },
                    {
                        'title': 'HTML Forms',
                        'content_type': 'QUIZ',
                        'order': 3,
                        'estimated_minutes': 20,
                        'is_published': True
                    }
                ]
            elif module.title == 'CSS Styling':
                lessons = [
                    {
                        'title': 'CSS Selectors',
                        'content_type': 'VIDEO',
                        'video_url': 'https://www.youtube.com/watch?v=yfoY53QXEnI',
                        'order': 1,
                        'estimated_minutes': 15,
                        'is_published': True
                    },
                    {
                        'title': 'Box Model',
                        'content_type': 'TEXT',
                        'content_text': 'The CSS box model consists of margins, borders, padding...',
                        'order': 2,
                        'estimated_minutes': 20,
                        'is_published': True
                    }
                ]
            elif module.title == 'JavaScript Basics':
                lessons = [
                    {
                        'title': 'Variables and Data Types',
                        'content_type': 'VIDEO',
                        'video_url': 'https://www.youtube.com/watch?v=W6NZfCO5SIk',
                        'order': 1,
                        'estimated_minutes': 25,
                        'is_published': True
                    },
                    {
                        'title': 'Functions',
                        'content_type': 'TEXT',
                        'content_text': 'Functions are reusable blocks of code...',
                        'order': 2,
                        'estimated_minutes': 30,
                        'is_published': True
                    }
                ]
            else:
                lessons = [
                    {
                        'title': f'Lesson 1: {module.title} Introduction',
                        'content_type': 'TEXT',
                        'content_text': f'Welcome to {module.title}...',
                        'order': 1,
                        'estimated_minutes': 15,
                        'is_published': True
                    }
                ]
            
            for lesson_data in lessons:
                lesson, created = Lesson.objects.get_or_create(
                    module=module,
                    title=lesson_data['title'],
                    defaults={
                        'content_type': lesson_data['content_type'],
                        'content_text': lesson_data.get('content_text', ''),
                        'video_url': lesson_data.get('video_url', ''),
                        'order': lesson_data['order'],
                        'estimated_minutes': lesson_data['estimated_minutes'],
                        'is_published': lesson_data['is_published']
                    }
                )
                if created:
                    print(f"    📝 Created lesson: {lesson.title}")
    
    # ============================================
    # 5. CREATE ENROLLMENTS WITH DIFFERENT RISK PROFILES
    # ============================================
    
    # Enroll all students in Web Development course
    web_course = courses[0]
    
    # Student profiles for risk demonstration
    enrollment_profiles = [
        {
            'student': students[0],  # James - High performing, low risk
            'progress': 85.5,
            'avg_quiz_score': 92.0,
            'last_activity': timezone.now() - timedelta(days=1),
            'risk_level': 'LOW',
            'risk_score': 0.15,
            'engagement_score': 0.85
        },
        {
            'student': students[1],  # Sarah - Medium risk, inconsistent
            'progress': 55.0,
            'avg_quiz_score': 68.5,
            'last_activity': timezone.now() - timedelta(days=5),
            'risk_level': 'MEDIUM',
            'risk_score': 0.55,
            'engagement_score': 0.45
        },
        {
            'student': students[2],  # Peter - High risk, falling behind
            'progress': 25.0,
            'avg_quiz_score': 45.0,
            'last_activity': timezone.now() - timedelta(days=14),
            'risk_level': 'HIGH',
            'risk_score': 0.82,
            'engagement_score': 0.20
        },
        {
            'student': students[3],  # Mary - Just enrolled, no activity
            'progress': 0.0,
            'avg_quiz_score': 0.0,
            'last_activity': timezone.now() - timedelta(days=2),
            'risk_level': 'MEDIUM',
            'risk_score': 0.45,
            'engagement_score': 0.10
        },
        {
            'student': students[4],  # David - Dropped out
            'progress': 15.0,
            'avg_quiz_score': 30.0,
            'last_activity': timezone.now() - timedelta(days=21),
            'status': Enrollment.Status.DROPPED,
            'risk_level': 'HIGH',
            'risk_score': 0.90,
            'engagement_score': 0.05
        }
    ]
    
    for profile in enrollment_profiles:
        enrollment, created = Enrollment.objects.get_or_create(
            student=profile['student'],
            course=web_course,
            defaults={
                'status': profile.get('status', Enrollment.Status.ACTIVE),
                'progress_percentage': profile['progress'],
                'average_quiz_score': profile['avg_quiz_score'],
                'last_activity': profile['last_activity'],
                'risk_level': profile['risk_level'],
                'risk_score': profile['risk_score'],
                'engagement_score': profile['engagement_score']
            }
        )
        
        if created:
            print(f"✅ Enrolled {profile['student'].display_name} in {web_course.title}")
            print(f"   Risk Level: {profile['risk_level']}, Progress: {profile['progress']}%")
    
    # ============================================
    # 6. CREATE LESSON COMPLETIONS
    # ============================================
    
    # James - Completed many lessons
    james = students[0]
    lessons = Lesson.objects.filter(module__course=web_course, is_published=True)[:8]
    for lesson in lessons:
        completion, created = LessonCompletion.objects.get_or_create(
            student=james,
            lesson=lesson,
            defaults={
                'completed_at': timezone.now() - timedelta(days=random.randint(1, 20)),
                'time_spent_seconds': random.randint(300, 900)
            }
        )
    
    # Sarah - Completed some lessons
    sarah = students[1]
    lessons = Lesson.objects.filter(module__course=web_course, is_published=True)[:4]
    for lesson in lessons:
        completion, created = LessonCompletion.objects.get_or_create(
            student=sarah,
            lesson=lesson,
            defaults={
                'completed_at': timezone.now() - timedelta(days=random.randint(3, 15)),
                'time_spent_seconds': random.randint(400, 1200)
            }
        )
    
    # Peter - Only completed first lesson
    peter = students[2]
    first_lesson = Lesson.objects.filter(
        module__course=web_course, 
        is_published=True
    ).order_by('order').first()
    
    if first_lesson:
        completion, created = LessonCompletion.objects.get_or_create(
            student=peter,
            lesson=first_lesson,
            defaults={
                'completed_at': timezone.now() - timedelta(days=25),
                'time_spent_seconds': 600
            }
        )
    
    print("=" * 50)
    print("✅ TEST DATA SEEDING COMPLETED SUCCESSFULLY!")
    print(f"📊 Summary:")
    print(f"   - Teachers: 1")
    print(f"   - Students: {len(students)}")
    print(f"   - Courses: {len(courses)}")
    print(f"   - Modules: {Module.objects.filter(course__teacher=teacher).count()}")
    print(f"   - Lessons: {Lesson.objects.filter(module__course__teacher=teacher).count()}")
    print(f"   - Enrollments: {Enrollment.objects.filter(course__teacher=teacher).count()}")
    print("=" * 50)

if __name__ == "__main__":
    import random
    create_test_data()