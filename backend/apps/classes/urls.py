from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ClassViewSet, ClassStudentViewSet, ClassScheduleViewSet,
    ClassAttendanceViewSet, ClassAnnouncementViewSet,
    ClassMaterialViewSet
)

router = DefaultRouter()
router.register('classes', ClassViewSet, basename='classes')
router.register('class-students', ClassStudentViewSet, basename='class-students')
router.register('class-schedules', ClassScheduleViewSet, basename='class-schedules')
router.register('class-attendances', ClassAttendanceViewSet, basename='class-attendances')
router.register('class-announcements', ClassAnnouncementViewSet, basename='class-announcements')
router.register('class-materials', ClassMaterialViewSet, basename='class-materials')

urlpatterns = [
    path('', include(router.urls)),
]
