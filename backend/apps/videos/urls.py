from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    VideoProgressViewSet, VideoProgressHistoryViewSet,
    VideoSourceViewSet, VideoSubtitleViewSet, WatchListViewSet
)

router = DefaultRouter()
router.register('progress', VideoProgressViewSet, basename='video-progress')
router.register('history', VideoProgressHistoryViewSet, basename='video-progress-history')
router.register('sources', VideoSourceViewSet, basename='video-sources')
router.register('subtitles', VideoSubtitleViewSet, basename='video-subtitles')
router.register('watch-lists', WatchListViewSet, basename='watch-lists')

urlpatterns = [
    path('', include(router.urls)),
]
