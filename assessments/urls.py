"""
Assessment URLs for Teachly
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import import_views

router = DefaultRouter()
router.register(r'quizzes', views.QuizViewSet, basename='quiz')
router.register(r'questions', views.QuestionViewSet, basename='question')
router.register(r'answers', views.AnswerViewSet, basename='answer')
router.register(r'attempts', views.QuizAttemptViewSet, basename='attempt')

urlpatterns = [
    path('', include(router.urls)),
    # CSV Import endpoints
    path('import/upload/', import_views.CSVImportAPIView.as_view(), name='csv_import_upload'),
    path('import/history/', import_views.import_history_list, name='csv_import_history_list'),
    path('import/history/<uuid:import_id>/', import_views.import_history_detail, name='csv_import_history_detail'),
    path('import/history/<uuid:import_id>/rollback/', import_views.rollback_import, name='csv_import_rollback'),
    path('import/record/<uuid:record_id>/edit/', import_views.edit_import_record, name='csv_import_record_edit'),
    path('import/record/<uuid:record_id>/delete/', import_views.delete_import_record, name='csv_import_record_delete'),
    path('import/history/<uuid:import_id>/download/', import_views.download_import_csv, name='csv_import_download'),
    path('import/template/', import_views.get_import_template, name='csv_import_template'),
]