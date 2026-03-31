"""
Assessment Admin Configuration
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Quiz, Question, Answer, QuizAttempt, QuestionResponse

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4
    fields = ['text', 'is_correct', 'order']

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ['text', 'question_type', 'points', 'order']
    show_change_link = True

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'lesson', 'is_published', 'total_questions', 'average_score', 'pass_rate']
    list_filter = ['is_published', 'quiz_type', 'created_at']
    search_fields = ['title', 'lesson__title']
    readonly_fields = ['total_questions', 'total_attempts', 'average_score', 'pass_rate']
    inlines = [QuestionInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('lesson', 'title', 'description', 'quiz_type')
        }),
        ('Settings', {
            'fields': ('time_limit_minutes', 'passing_score', 'max_attempts', 
                      'shuffle_questions', 'show_answers', 'is_published')
        }),
        ('Statistics', {
            'fields': ('total_questions', 'total_attempts', 'average_score', 'pass_rate'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['short_text', 'quiz', 'question_type', 'points', 'difficulty_index', 'correct_rate']
    list_filter = ['question_type', 'quiz']
    search_fields = ['text', 'quiz__title']
    readonly_fields = ['difficulty_index', 'times_answered', 'times_correct', 'correct_rate']
    inlines = [AnswerInline]
    
    def short_text(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    short_text.short_description = 'Question'
    
    def correct_rate(self, obj):
        return f"{obj.correct_rate:.1f}%"
    correct_rate.short_description = 'Correct Rate'

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['short_text', 'question', 'is_correct', 'order']
    list_filter = ['is_correct', 'question__quiz']
    search_fields = ['text', 'question__text']
    
    def short_text(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    short_text.short_description = 'Answer'

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['student', 'quiz', 'attempt_number', 'score_percentage', 'passed', 'submitted_at']
    list_filter = ['passed', 'status', 'quiz']
    search_fields = ['student__email', 'quiz__title']
    readonly_fields = ['score', 'score_percentage', 'max_possible_score', 'time_spent_seconds']
    date_hierarchy = 'submitted_at'
    
    def colored_score(self, obj):
        color = 'green' if obj.passed else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color,
            obj.score_percentage
        )
    colored_score.short_description = 'Score'
    colored_score.admin_order_field = 'score_percentage'

@admin.register(QuestionResponse)
class QuestionResponseAdmin(admin.ModelAdmin):
    list_display = ['attempt', 'question', 'is_correct', 'created_at']
    list_filter = ['is_correct', 'created_at']
    search_fields = ['attempt__student__email', 'question__text']
    readonly_fields = ['created_at']