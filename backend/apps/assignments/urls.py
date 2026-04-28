from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssignmentViewSet, AssignmentSubmissionViewSet

router = DefaultRouter()
router.register('assignments', AssignmentViewSet, basename='assignments')
router.register('submissions', AssignmentSubmissionViewSet, basename='assignment-submissions')

urlpatterns = [
    path('', include(router.urls)),
]
