from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Sum, Count

from .models import (
    VideoProgress, VideoProgressHistory, VideoSource, 
    VideoSubtitle, WatchList, WatchListItem
)
from .serializers import (
    VideoProgressSerializer, VideoProgressHistorySerializer,
    VideoSourceSerializer, VideoSubtitleSerializer,
    WatchListSerializer, WatchListCreateSerializer,
    WatchListItemSerializer, VideoProgressCreateSerializer
)
from apps.courses.models import Lesson, CourseEnrollment
from edu_platform.permissions import (
    IsStudent, IsCourseStudent, IsOwnerOrReadOnly
)


class VideoProgressViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VideoProgressSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['lesson', 'is_completed']
    ordering_fields = ['last_watched_at', 'progress', 'created_at']
    ordering = ['-last_watched_at']

    def get_queryset(self):
        return VideoProgress.objects.filter(
            student=self.request.user
        ).select_related(
            'lesson', 'lesson__chapter', 'lesson__chapter__course'
        )

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def sync(self, request):
        serializer = VideoProgressCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        lesson_id = serializer.validated_data['lesson_id']
        current_time = serializer.validated_data['current_time']
        total_duration = serializer.validated_data['total_duration']
        playback_rate = serializer.validated_data.get('playback_rate', 1.0)
        is_seeked = serializer.validated_data.get('is_seeked', False)
        seek_from = serializer.validated_data.get('seek_from')
        seek_to = serializer.validated_data.get('seek_to')
        is_playing = serializer.validated_data.get('is_playing', True)
        
        try:
            lesson = Lesson.objects.select_related('chapter__course').get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {'error': '课时不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not lesson.is_free:
            has_enrollment = CourseEnrollment.objects.filter(
                course=lesson.chapter.course,
                student=request.user,
                is_active=True
            ).exists()
            
            if not has_enrollment and not (
                request.user.role in ['teacher', 'admin'] or request.user.is_superuser
            ):
                return Response(
                    {'error': '您没有权限观看此视频'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        progress, created = VideoProgress.objects.get_or_create(
            lesson=lesson,
            student=request.user,
            defaults={
                'current_time': current_time,
                'total_duration': total_duration,
                'progress': min(current_time / total_duration if total_duration > 0 else 0, 1.0),
                'play_count': 1
            }
        )
        
        if not created:
            time_diff = current_time - progress.current_time
            
            if is_playing and not is_seeked and time_diff > 0:
                progress.watch_duration += time_diff
            
            progress.current_time = current_time
            progress.total_duration = total_duration
            progress.progress = min(current_time / total_duration if total_duration > 0 else 0, 1.0)
            
            if is_playing and current_time < 5:
                progress.play_count += 1
            
            progress.save()
        
        if is_playing:
            from_time = progress.current_time - 5 if progress.current_time > 5 else 0
            VideoProgressHistory.objects.create(
                video_progress=progress,
                from_time=seek_from if is_seeked else from_time,
                to_time=seek_to if is_seeked else current_time,
                duration=current_time - from_time if not is_seeked else 0,
                playback_rate=playback_rate,
                is_seeked=is_seeked,
                seek_from=seek_from,
                seek_to=seek_to
            )
        
        from django.conf import settings
        threshold = getattr(settings, 'VIDEO_COMPLETION_THRESHOLD', 0.9)
        is_complete = progress.progress >= threshold
        
        if is_complete and not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = timezone.now()
            progress.save()
            
            course = lesson.chapter.course
            enrollment = CourseEnrollment.objects.filter(
                course=course,
                student=request.user
            ).first()
            
            if enrollment:
                total_lessons = course.lessons.count()
                completed_lessons = VideoProgress.objects.filter(
                    lesson__chapter__course=course,
                    student=request.user,
                    is_completed=True
                ).count()
                
                enrollment.progress = completed_lessons / total_lessons if total_lessons > 0 else 0
                
                if enrollment.progress >= 1.0:
                    enrollment.is_completed = True
                    enrollment.completed_at = timezone.now()
                
                enrollment.save()
        
        return Response(VideoProgressSerializer(progress).data)

    @action(detail=False, methods=['get'])
    def recent(self, request):
        progresses = self.get_queryset()[:10]
        serializer = self.get_serializer(progresses, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        progresses = self.get_queryset()
        
        total_watch_time = progresses.aggregate(total=Sum('watch_duration'))['total'] or 0
        total_lessons = progresses.count()
        completed_lessons = progresses.filter(is_completed=True).count()
        
        return Response({
            'total_watch_time_seconds': total_watch_time,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'completion_rate': completed_lessons / total_lessons if total_lessons > 0 else 0
        })


class VideoProgressHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VideoProgressHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['video_progress']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return VideoProgressHistory.objects.filter(
            video_progress__student=self.request.user
        ).select_related('video_progress')


class VideoSourceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VideoSource.objects.filter(is_active=True)
    serializer_class = VideoSourceSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['lesson', 'quality']


class VideoSubtitleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VideoSubtitle.objects.filter(is_active=True)
    serializer_class = VideoSubtitleSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['lesson', 'language']


class WatchListViewSet(viewsets.ModelViewSet):
    serializer_class = WatchListSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_public', 'is_default']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return WatchListCreateSerializer
        return WatchListSerializer

    def get_queryset(self):
        return WatchList.objects.filter(
            student=self.request.user
        ).prefetch_related('items', 'items__lesson')

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)

    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        watch_list = self.get_object()
        lesson_id = request.data.get('lesson_id')
        
        if not lesson_id:
            return Response(
                {'error': '请提供课时ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {'error': '课时不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if WatchListItem.objects.filter(watch_list=watch_list, lesson=lesson).exists():
            return Response(
                {'error': '该课时已在播放列表中'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        last_item = watch_list.items.order_by('-item_order').first()
        item_order = last_item.item_order + 1 if last_item else 0
        
        item = WatchListItem.objects.create(
            watch_list=watch_list,
            lesson=lesson,
            item_order=item_order
        )
        
        return Response(WatchListItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def remove_item(self, request, pk=None):
        watch_list = self.get_object()
        item_id = request.data.get('item_id')
        
        if not item_id:
            return Response(
                {'error': '请提供播放列表项ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            item = WatchListItem.objects.get(id=item_id, watch_list=watch_list)
        except WatchListItem.DoesNotExist:
            return Response(
                {'error': '播放列表项不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        item.delete()
        return Response({'message': '已从播放列表中移除'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def reorder_items(self, request, pk=None):
        watch_list = self.get_object()
        items_order = request.data.get('items_order', [])
        
        if not items_order:
            return Response(
                {'error': '请提供排序数据'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        for item_data in items_order:
            item_id = item_data.get('item_id')
            item_order = item_data.get('item_order')
            
            try:
                item = WatchListItem.objects.get(id=item_id, watch_list=watch_list)
                item.item_order = item_order
                item.save()
            except WatchListItem.DoesNotExist:
                continue
        
        return Response({'message': '排序已更新'})
