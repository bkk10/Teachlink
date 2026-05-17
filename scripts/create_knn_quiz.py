"""
Create missing quiz for KNN lesson to fix the data integrity issue.
This creates a placeholder quiz that teachers can then add questions to.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from courses.models import Lesson
from assessments.models import Quiz

def create_knn_quiz():
    # Find the KNN lesson
    knn_lesson = Lesson.objects.filter(title__iexact='KNN').first()
    
    if not knn_lesson:
        print("❌ KNN lesson not found")
        return
    
    print(f"📚 Found KNN lesson: {knn_lesson.title}")
    print(f"   Course: {knn_lesson.module.course.title}")
    
    # Check if quiz already exists
    existing_quiz = Quiz.objects.filter(lesson=knn_lesson).first()
    if existing_quiz:
        print(f"✅ Quiz already exists: {existing_quiz.title}")
        print(f"   Questions: {existing_quiz.total_questions}")
        print(f"   Published: {existing_quiz.is_published}")
        return
    
    # Create a placeholder quiz
    quiz = Quiz.objects.create(
        lesson=knn_lesson,
        title=f'{knn_lesson.title} Quiz',
        description='K-Nearest Neighbors assessment',
        quiz_type='MCQ',
        passing_score=70,
        time_limit_minutes=30,
        max_attempts=3,
        is_published=False,  # Not published until questions are added
        total_questions=0,
    )
    
    print(f"✅ Created quiz for KNN lesson:")
    print(f"   ID: {quiz.id}")
    print(f"   Title: {quiz.title}")
    print(f"   Status: Draft (add questions to publish)")
    print(f"\n⚠️  Note: The teacher needs to add questions to this quiz.")
    print(f"   The quiz is currently unpublished (is_published=False)")

if __name__ == '__main__':
    create_knn_quiz()
