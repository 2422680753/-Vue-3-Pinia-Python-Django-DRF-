from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExamViewSet, ExamAttemptViewSet, QuestionBankViewSet
)

router = DefaultRouter()
router.register('exams', ExamViewSet, basename='exams')
router.register('attempts', ExamAttemptViewSet, basename='exam-attempts')
router.register('question-bank', QuestionBankViewSet, basename='question-bank')

urlpatterns = [
    path('', include(router.urls)),
]
