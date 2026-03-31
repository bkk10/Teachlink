"""
Course Management Admin Configuration
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Course, Module, Lesson, LessonCompletion, Enrollment

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'teacher', 'status', 'total_students', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'teacher__email']
    date_hierarchy = 'created_at'
    
    def total_students(self, obj):
        return obj.total_students
    total_students.short_description = 'Students'

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order', 'total_lessons']
    list_filter = ['course']
    search_fields = ['title', 'course__title']

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'module', 'content_type', 'is_published', 'difficulty_level']
    list_filter = ['content_type', 'is_published', 'difficulty_level']
    search_fields = ['title', 'module__title']
    readonly_fields = ['difficulty_score', 'difficulty_level']

@admin.register(LessonCompletion)
class LessonCompletionAdmin(admin.ModelAdmin):
    list_display = ['student', 'lesson', 'completed_at']
    list_filter = ['completed_at']
    search_fields = ['student__email', 'lesson__title']
    date_hierarchy = 'completed_at'

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'progress_percentage', 'risk_level', 'last_activity']
    list_filter = ['status', 'risk_level', 'enrolled_at']
    search_fields = ['student__email', 'course__title']
    readonly_fields = ['risk_score', 'engagement_score']
    
    def colored_risk(self, obj):
        colors = {
            'LOW': 'green',
            'MEDIUM': 'orange',
            'HIGH': 'red',
            'UNKNOWN': 'gray'
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.risk_level, 'black'),
            obj.get_risk_level_display()
        )
    colored_risk.short_description = 'Risk Level'
    colored_risk.admin_order_field = 'risk_level'