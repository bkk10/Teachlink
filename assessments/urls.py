"""
Assessment URLs for TeachLink
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'quizzes', views.QuizViewSet, basename='quiz')
router.register(r'questions', views.QuestionViewSet, basename='question')
router.register(r'answers', views.AnswerViewSet, basename='answer')
router.register(r'attempts', views.QuizAttemptViewSet, basename='attempt')

urlpatterns = [
    path('', include(router.urls)),
]