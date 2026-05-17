"""
Diagnostic script to check for duplicate lessons in courses.
Run this to identify data issues causing duplicate lesson entries.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachlink.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from courses.models import Course, Lesson, Module
from collections import defaultdict

def check_duplicate_lessons():
    """Check for lessons with the same title in the same course."""
    print("=" * 80)
    print("LESSON DUPLICATE ANALYSIS")
    print("=" * 80)
    
    courses = Course.objects.all()
    
    for course in courses:
        lessons = Lesson.objects.filter(module__course=course).select_related('module')
        
        # Check for duplicate titles
        title_counts = defaultdict(list)
        for lesson in lessons:
            title_counts[lesson.title].append({
                'id': lesson.id,
                'module': lesson.module.title,
                'order': lesson.order,
                'has_file': bool(lesson.resource_file),
                'has_html': bool(lesson.content_html),
                'has_quiz': hasattr(lesson, 'quiz')
            })
        
        duplicates_found = False
        for title, items in title_counts.items():
            if len(items) > 1:
                if not duplicates_found:
                    print(f"\n📚 Course: {course.title} (ID: {course.id})")
                    duplicates_found = True
                print(f"  ⚠️  Duplicate title: '{title}' appears {len(items)} times")
                for item in items:
                    content_types = []
                    if item['has_file']:
                        content_types.append('FILE')
                    if item['has_html']:
                        content_types.append('HTML')
                    if item['has_quiz']:
                        content_types.append('QUIZ')
                    content_str = ', '.join(content_types) if content_types else 'EMPTY'
                    print(f"      - ID: {item['id']}, Module: {item['module']}, Order: {item['order']}, Content: [{content_str}]")
        
        if not duplicates_found:
            print(f"\n✅ Course: {course.title} - No duplicate titles found ({lessons.count()} lessons)")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total_lessons = Lesson.objects.count()
    unique_titles = Lesson.objects.values('module__course', 'title').distinct().count()
    print(f"Total lessons: {total_lessons}")
    print(f"Unique (course+title) combinations: {unique_titles}")
    
    if total_lessons != unique_titles:
        print(f"⚠️  Found {total_lessons - unique_titles} potential duplicates")
    else:
        print("✅ No duplicate titles found across all courses")

if __name__ == '__main__':
    check_duplicate_lessons()
