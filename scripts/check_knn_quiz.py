"""
Check KNN lesson and quiz data to diagnose missing quiz issue.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from courses.models import Lesson, Module, Course
from assessments.models import Quiz

def check_knn_lesson():
    # Find lessons with "KNN" or "knn" in the title
    knn_lessons = Lesson.objects.filter(title__icontains='knn')
    
    print("=" * 80)
    print("KNN LESSON ANALYSIS")
    print("=" * 80)
    
    for lesson in knn_lessons:
        print(f"\n📚 Lesson: {lesson.title}")
        print(f"   ID: {lesson.id}")
        print(f"   Module: {lesson.module.title}")
        print(f"   Course: {lesson.module.course.title}")
        print(f"   Has resource_file: {bool(lesson.resource_file)}")
        print(f"   Has content_html: {bool(lesson.content_html)}")
        
        # Check for quiz
        quiz = Quiz.objects.filter(lesson=lesson).first()
        if quiz:
            print(f"   ✅ Quiz: {quiz.title}")
            print(f"      - ID: {quiz.id}")
            print(f"      - Type: {quiz.quiz_type}")
            print(f"      - is_published: {quiz.is_published}")
            print(f"      - total_questions: {quiz.total_questions}")
            print(f"      - passing_score: {quiz.passing_score}")
        else:
            print(f"   ❌ No quiz attached to this lesson")
    
    if not knn_lessons:
        print("\n❌ No lessons with 'KNN' in title found")
        
    # Also check for "K-Nearest Neighbors" or similar
    similar_lessons = Lesson.objects.filter(title__icontains='nearest')
    if similar_lessons:
        print(f"\n📚 Found {similar_lessons.count()} lessons with 'nearest' in title:")
        for lesson in similar_lessons:
            print(f"   - {lesson.title} (Course: {lesson.module.course.title})")

if __name__ == '__main__':
    check_knn_lesson()
