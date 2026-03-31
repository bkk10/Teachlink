#!/usr/bin/env python
"""
Add performance indexes to database
Run: python manage.py shell < scripts/add_indexes.py
"""
import django
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachlink.settings.development')
django.setup()

from django.db import connection

def add_indexes():
    print("=" * 60)
    print("📊 ADDING DATABASE INDEXES")
    print("=" * 60)
    
    # SQLite doesn't support IF NOT EXISTS in CREATE INDEX
    # So we'll check if indexes exist first
    with connection.cursor() as cursor:
        # Get existing indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        existing_indexes = [row[0] for row in cursor.fetchall()]
        print(f"📋 Found {len(existing_indexes)} existing indexes")
    
    indexes = [
        # Users app
        {
            'name': 'idx_users_email',
            'sql': "CREATE INDEX idx_users_email ON users (email);",
            'table': 'users'
        },
        {
            'name': 'idx_users_role',
            'sql': "CREATE INDEX idx_users_role ON users (role);",
            'table': 'users'
        },
        {
            'name': 'idx_users_last_activity',
            'sql': "CREATE INDEX idx_users_last_activity ON users (last_activity);",
            'table': 'users'
        },
        
        # Courses app
        {
            'name': 'idx_courses_teacher_status',
            'sql': "CREATE INDEX idx_courses_teacher_status ON courses (teacher_id, status);",
            'table': 'courses'
        },
        {
            'name': 'idx_modules_course_order',
            'sql': 'CREATE INDEX idx_modules_course_order ON modules (course_id, "order");',
            'table': 'modules'
        },
        {
            'name': 'idx_lessons_module_order',
            'sql': 'CREATE INDEX idx_lessons_module_order ON lessons (module_id, "order");',
            'table': 'lessons'
        },
        {
            'name': 'idx_lessons_difficulty',
            'sql': "CREATE INDEX idx_lessons_difficulty ON lessons (difficulty_level);",
            'table': 'lessons'
        },
        
        # Enrollments
        {
            'name': 'idx_enrollments_student_status',
            'sql': "CREATE INDEX idx_enrollments_student_status ON enrollments (student_id, status);",
            'table': 'enrollments'
        },
        {
            'name': 'idx_enrollments_course_status',
            'sql': "CREATE INDEX idx_enrollments_course_status ON enrollments (course_id, status);",
            'table': 'enrollments'
        },
        {
            'name': 'idx_enrollments_risk',
            'sql': "CREATE INDEX idx_enrollments_risk ON enrollments (risk_level, last_activity);",
            'table': 'enrollments'
        },
        {
            'name': 'idx_enrollments_last_activity',
            'sql': "CREATE INDEX idx_enrollments_last_activity ON enrollments (last_activity);",
            'table': 'enrollments'
        },
        
        # Lesson completions
        {
            'name': 'idx_completions_student_date',
            'sql': "CREATE INDEX idx_completions_student_date ON lesson_completions (student_id, completed_at);",
            'table': 'lesson_completions'
        },
        {
            'name': 'idx_completions_lesson_date',
            'sql': "CREATE INDEX idx_completions_lesson_date ON lesson_completions (lesson_id, completed_at);",
            'table': 'lesson_completions'
        },
        
        # Quiz attempts
        {
            'name': 'idx_quiz_attempts_student_quiz',
            'sql': "CREATE INDEX idx_quiz_attempts_student_quiz ON quiz_attempts (student_id, quiz_id);",
            'table': 'quiz_attempts'
        },
        {
            'name': 'idx_quiz_attempts_quiz_status',
            'sql': "CREATE INDEX idx_quiz_attempts_quiz_status ON quiz_attempts (quiz_id, status);",
            'table': 'quiz_attempts'
        },
        {
            'name': 'idx_quiz_attempts_submitted',
            'sql': "CREATE INDEX idx_quiz_attempts_submitted ON quiz_attempts (submitted_at);",
            'table': 'quiz_attempts'
        },
        
        # Analytics
        {
            'name': 'idx_risk_history_student_date',
            'sql': "CREATE INDEX idx_risk_history_student_date ON risk_history (student_id, calculated_at);",
            'table': 'risk_history'
        },
        {
            'name': 'idx_risk_history_course_level',
            'sql': "CREATE INDEX idx_risk_history_course_level ON risk_history (course_id, risk_level);",
            'table': 'risk_history'
        },
        {
            'name': 'idx_alerts_teacher_status',
            'sql': "CREATE INDEX idx_alerts_teacher_status ON alerts (teacher_id, status);",
            'table': 'alerts'
        },
        {
            'name': 'idx_alerts_student_status',
            'sql': "CREATE INDEX idx_alerts_student_status ON alerts (student_id, status);",
            'table': 'alerts'
        },
        {
            'name': 'idx_alerts_generated',
            'sql': "CREATE INDEX idx_alerts_generated ON alerts (generated_at);",
            'table': 'alerts'
        },
        
        # Lesson difficulty
        {
            'name': 'idx_lesson_difficulty_score',
            'sql': "CREATE INDEX idx_lesson_difficulty_score ON lesson_difficulty (difficulty_score DESC);",
            'table': 'lesson_difficulty'
        },
        {
            'name': 'idx_lesson_difficulty_level',
            'sql': "CREATE INDEX idx_lesson_difficulty_level ON lesson_difficulty (difficulty_level);",
            'table': 'lesson_difficulty'
        },
        
        # Engagement metrics
        {
            'name': 'idx_engagement_student_date',
            'sql': "CREATE INDEX idx_engagement_student_date ON engagement_metrics (student_id, date DESC);",
            'table': 'engagement_metrics'
        },
        {
            'name': 'idx_engagement_course_level',
            'sql': "CREATE INDEX idx_engagement_course_level ON engagement_metrics (course_id, engagement_level);",
            'table': 'engagement_metrics'
        },
    ]
    
    with connection.cursor() as cursor:
        for index in indexes:
            try:
                # Check if index already exists
                if index['name'] in existing_indexes:
                    print(f"⏭️  {index['table']}: {index['name']} already exists")
                    continue
                
                cursor.execute(index['sql'])
                print(f"✅ {index['table']}: {index['name']}")
            except Exception as e:
                print(f"⚠️  {index['table']}: {index['name']} - {e}")
    
    # Verify indexes were created
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        final_indexes = [row[0] for row in cursor.fetchall()]
        new_count = len(final_indexes) - len(existing_indexes)
    
    print(f"\n📊 Index Summary:")
    print(f"   • Existing indexes: {len(existing_indexes)}")
    print(f"   • New indexes added: {new_count}")
    print(f"   • Total indexes: {len(final_indexes)}")
    print("\n✅ Database optimization complete!")

if __name__ == "__main__":
    add_indexes()