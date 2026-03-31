from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Quiz, Question, Answer, QuizAttempt

@receiver(post_save, sender=Question)
@receiver(post_delete, sender=Question)
def update_quiz_question_count(sender, instance, **kwargs):
    """Update quiz total_questions when questions are added/removed"""
    quiz = instance.quiz
    quiz.total_questions = quiz.questions.count()
    quiz.save(update_fields=['total_questions'])

@receiver(post_save, sender=QuizAttempt)
def update_quiz_statistics_on_attempt(sender, instance, **kwargs):
    """Update quiz statistics when a new attempt is completed"""
    if instance.status == QuizAttempt.Status.COMPLETED:
        instance.quiz.update_statistics()