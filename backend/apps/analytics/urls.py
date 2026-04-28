from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LearningSessionViewSet, DailyLearningStatsViewSet,
    CourseProgressStatsViewSet, LearningBehaviorViewSet,
    LearningAnalyticsViewSet, ClassAnalyticsViewSet
)

router = DefaultRouter()
router.register('learning-sessions', LearningSessionViewSet, basename='learning-sessions')
router.register('daily-stats', DailyLearningStatsViewSet, basename='daily-stats')
router.register('course-progress', CourseProgressStatsViewSet, basename='course-progress')
router.register('learning-behaviors', LearningBehaviorViewSet, basename='learning-behaviors')
router.register('learning-analytics', LearningAnalyticsViewSet, basename='learning-analytics')
router.register('class-analytics', ClassAnalyticsViewSet, basename='class-analytics')

urlpatterns = [
    path('', include(router.urls)),
]
