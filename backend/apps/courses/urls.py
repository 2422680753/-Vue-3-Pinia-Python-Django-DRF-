from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, TagViewSet, CourseViewSet, ChapterViewSet,
    LessonViewSet, MyCoursesView, LiveCourseViewSet
)

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='categories')
router.register('tags', TagViewSet, basename='tags')
router.register('courses', CourseViewSet, basename='courses')
router.register('chapters', ChapterViewSet, basename='chapters')
router.register('lessons', LessonViewSet, basename='lessons')
router.register('live', LiveCourseViewSet, basename='live-courses')

urlpatterns = [
    path('my-courses/', MyCoursesView.as_view(), name='my-courses'),
    path('', include(router.urls)),
]
