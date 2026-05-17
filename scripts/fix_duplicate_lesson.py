"""
Script to remove the duplicate empty lesson from Demo Course 3.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from courses.models import Lesson

def remove_empty_duplicate():
    # Find the empty duplicate of "Introduction to machine learning"
    lessons = Lesson.objects.filter(
        title='Introduction to machine learning',
        module__course__title='Demo Course 3'
    )
    
    print(f"Found {lessons.count()} lessons with title 'Introduction to machine learning'")
    
    for lesson in lessons:
        has_content = bool(lesson.resource_file or lesson.content_html or lesson.video_url or lesson.external_url)
        has_quiz = hasattr(lesson, 'quiz')
        print(f"  - ID: {lesson.id}, Module: {lesson.module.title}, Has content: {has_content}, Has quiz: {has_quiz}")
        
        if not has_content and not has_quiz:
            print(f"    → Removing empty lesson {lesson.id}")
            lesson.delete()
            print(f"    → Deleted successfully")

if __name__ == '__main__':
    remove_empty_duplicate()
