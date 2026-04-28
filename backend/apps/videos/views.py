import uuid
from datetime import timedelta
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db.models import Sum, Count
from django.conf import settings

from .models import (
    VideoProgress, VideoProgressHistory, VideoProgressConflict, 
    VideoWatchSession, VideoSource, VideoSubtitle, WatchList, WatchListItem
)
from .serializers import (
    VideoProgressSerializer, VideoProgressHistorySerializer,
    VideoProgressSyncSerializer, VideoProgressBatchSerializer,
    VideoSourceSerializer, VideoSubtitleSerializer,
    WatchListSerializer, WatchListCreateSerializer,
    WatchListItemSerializer
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
    
    @action(detail=False, methods=['get'], url_path='by-lesson/(?P<lesson_id>\d+)')
    def get_by_lesson(self, request, lesson_id=None):
        try:
            progress = VideoProgress.objects.get(
                lesson_id=lesson_id,
                student=request.user
            )
            serializer = self.get_serializer(progress)
            
            active_session = VideoWatchSession.objects.filter(
                video_progress=progress,
                is_active=True
            ).first()
            
            data = serializer.data
            data['active_session'] = {
                'session_id': active_session.session_id if active_session else None,
                'start_time': active_session.start_time.isoformat() if active_session else None
            }
            
            return Response(data)
        except VideoProgress.DoesNotExist:
            return Response({
                'exists': False,
                'current_time': 0,
                'progress': 0,
                'is_completed': False
            })

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def sync(self, request):
        serializer = VideoProgressSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        lesson_id = serializer.validated_data['lesson_id']
        current_time = serializer.validated_data['current_time']
        total_duration = serializer.validated_data['total_duration']
        playback_rate = serializer.validated_data.get('playback_rate', 1.0)
        is_seeked = serializer.validated_data.get('is_seeked', False)
        seek_from = serializer.validated_data.get('seek_from')
        seek_to = serializer.validated_data.get('seek_to')
        is_playing = serializer.validated_data.get('is_playing', True)
        request_id = serializer.validated_data.get('request_id')
        client_version = serializer.validated_data.get('client_version')
        session_id = serializer.validated_data.get('session_id')
        
        try:
            lesson = Lesson.objects.select_related('chapter__course').get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {'error': '课时不存在', 'error_code': 'LESSON_NOT_FOUND'},
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
                    {'error': '您没有权限观看此视频', 'error_code': 'NO_PERMISSION'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        new_progress = min(current_time / total_duration if total_duration > 0 else 0, 1.0)
        
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        device_info = self._parse_device_info(user_agent)
        
        if request_id:
            existing_history = VideoProgressHistory.objects.filter(request_id=request_id).first()
            if existing_history:
                progress = existing_history.video_progress
                return Response({
                    **VideoProgressSerializer(progress).data,
                    'is_idempotent': True,
                    'request_id': request_id
                })
        
        with transaction.atomic():
            try:
                progress, created = VideoProgress.objects.select_for_update(skip_locked=True).get_or_create(
                    lesson=lesson,
                    student=request.user,
                    defaults={
                        'current_time': current_time,
                        'total_duration': total_duration,
                        'progress': new_progress,
                        'play_count': 1,
                        'version': 1,
                        'last_update_ip': ip_address,
                    }
                )
            except IntegrityError:
                progress = VideoProgress.objects.select_for_update().get(
                    lesson=lesson,
                    student=request.user
                )
                created = False
            
            if not created:
                if progress.is_completed:
                    return Response({
                        **VideoProgressSerializer(progress).data,
                        'is_completed': True,
                        'warning': '课程已完成，进度不再更新'
                    })
                
                server_time = progress.current_time
                server_progress = progress.progress
                
                time_forward = current_time > server_time
                progress_forward = new_progress > server_progress
                
                time_backward_threshold = getattr(settings, 'VIDEO_ALLOWED_BACKWARD_SECONDS', 300)
                is_valid_backward = (server_time - current_time) <= time_backward_threshold
                
                should_update = False
                conflict_type = None
                conflict_resolution = None
                
                if time_forward or progress_forward:
                    should_update = True
                elif is_valid_backward:
                    should_update = True
                elif current_time < server_time - time_backward_threshold:
                    conflict_type = 'time_backward'
                    should_update = False
                    conflict_resolution = {
                        'action': 'reject',
                        'reason': '时间回退超过阈值',
                        'server_time': server_time,
                        'client_time': current_time,
                        'allowed_threshold': time_backward_threshold
                    }
                
                if client_version and client_version < progress.version:
                    conflict_type = 'version_mismatch'
                    should_update = False
                    conflict_resolution = {
                        'action': 'sync_required',
                        'server_version': progress.version,
                        'client_version': client_version
                    }
                
                if conflict_type and not should_update:
                    VideoProgressConflict.objects.create(
                        video_progress=progress,
                        conflict_type=conflict_type,
                        server_state={
                            'current_time': server_time,
                            'progress': server_progress,
                            'version': progress.version,
                            'last_update_time': progress.last_update_time.isoformat()
                        },
                        client_state={
                            'current_time': current_time,
                            'progress': new_progress,
                            'version': client_version,
                            'request_id': request_id,
                            'session_id': session_id
                        },
                        resolution=conflict_resolution,
                        is_resolved=True,
                        resolved_at=timezone.now(),
                        session_id=session_id,
                        ip_address=ip_address,
                        device_info=device_info
                    )
                    
                    return Response({
                        **VideoProgressSerializer(progress).data,
                        'conflict': {
                            'type': conflict_type,
                            'resolution': conflict_resolution
                        }
                    }, status=status.HTTP_200_OK)
                
                if should_update:
                    time_diff = current_time - server_time
                    
                    if is_playing and not is_seeked and time_diff > 0:
                        effective_watch = time_diff / max(playback_rate, 0.5)
                        progress.watch_duration += effective_watch
                    
                    progress.current_time = current_time
                    progress.total_duration = total_duration
                    progress.progress = new_progress
                    progress.version += 1
                    progress.last_update_client = device_info
                    progress.last_update_ip = ip_address
                    
                    if is_playing and current_time < 5:
                        progress.play_count += 1
                    
                    progress.save()
                
                self._manage_session(progress, session_id, current_time, is_playing, ip_address, user_agent, device_info)
        
        if is_playing or is_seeked:
            from_time = max(0, (progress.current_time if created else server_time) - 5)
            try:
                VideoProgressHistory.objects.create(
                    video_progress=progress,
                    from_time=seek_from if is_seeked else from_time,
                    to_time=seek_to if is_seeked else current_time,
                    duration=current_time - from_time if not is_seeked else 0,
                    playback_rate=playback_rate,
                    is_seeked=is_seeked,
                    seek_from=seek_from,
                    seek_to=seek_to,
                    session_id=session_id,
                    request_id=request_id,
                    ip_address=ip_address,
                    device_info=device_info,
                    user_agent=user_agent
                )
            except IntegrityError:
                pass
        
        threshold = getattr(settings, 'VIDEO_COMPLETION_THRESHOLD', 0.9)
        is_complete = progress.progress >= threshold
        
        if is_complete and not progress.is_completed:
            with transaction.atomic():
                progress.is_completed = True
                progress.completed_at = timezone.now()
                progress.save()
                
                self._update_course_progress(progress)
        
        response_data = VideoProgressSerializer(progress).data
        response_data['server_time'] = timezone.now().isoformat()
        if request_id:
            response_data['request_id'] = request_id
        
        return Response(response_data)
    
    @action(detail=False, methods=['post'], url_path='batch-sync')
    def batch_sync(self, request):
        serializer = VideoProgressBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        items = serializer.validated_data['items']
        results = []
        
        for item in items:
            try:
                response = self._sync_single_item(request, item)
                results.append(response)
            except Exception as e:
                results.append({
                    'lesson_id': item.get('lesson_id'),
                    'error': str(e),
                    'success': False
                })
        
        return Response({'results': results})
    
    @action(detail=False, methods=['post'], url_path='session-start')
    def start_session(self, request):
        lesson_id = request.data.get('lesson_id')
        if not lesson_id:
            return Response(
                {'error': '请提供课时ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            progress, created = VideoProgress.objects.get_or_create(
                lesson_id=lesson_id,
                student=request.user,
                defaults={
                    'current_time': 0,
                    'total_duration': 0,
                    'progress': 0,
                    'version': 1
                }
            )
        except VideoProgress.DoesNotExist:
            return Response(
                {'error': '课时不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        device_info = self._parse_device_info(user_agent)
        
        active_sessions = VideoWatchSession.objects.filter(
            video_progress=progress,
            is_active=True
        )
        
        for session in active_sessions:
            session.is_active = False
            session.end_time = timezone.now()
            session.final_time = progress.current_time
            session.save()
        
        session_id = f'sess_{uuid.uuid4().hex[:16]}'
        session = VideoWatchSession.objects.create(
            video_progress=progress,
            session_id=session_id,
            initial_time=progress.current_time,
            ip_address=ip_address,
            device_info=device_info,
            user_agent=user_agent
        )
        
        return Response({
            'session_id': session_id,
            'start_time': session.start_time.isoformat(),
            'current_time': progress.current_time,
            'progress': progress.progress,
            'is_completed': progress.is_completed,
            'version': progress.version,
            'total_duration': progress.total_duration,
            'active_sessions_terminated': active_sessions.count()
        })
    
    @action(detail=False, methods=['post'], url_path='session-heartbeat')
    def session_heartbeat(self, request):
        session_id = request.data.get('session_id')
        if not session_id:
            return Response(
                {'error': '请提供会话ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            session = VideoWatchSession.objects.get(
                session_id=session_id,
                is_active=True
            )
            session.update_heartbeat()
            
            return Response({
                'session_id': session_id,
                'status': 'active',
                'last_heartbeat': session.last_heartbeat.isoformat(),
                'server_time': timezone.now().isoformat()
            })
        except VideoWatchSession.DoesNotExist:
            return Response(
                {'error': '会话不存在或已结束'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'], url_path='session-end')
    def end_session(self, request):
        session_id = request.data.get('session_id')
        final_time = request.data.get('final_time')
        
        if not session_id:
            return Response(
                {'error': '请提供会话ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            session = VideoWatchSession.objects.get(session_id=session_id)
            progress = session.video_progress
            
            if final_time is not None:
                session.final_time = final_time
                
                time_diff = final_time - session.initial_time
                if time_diff > 0:
                    session.total_seconds = time_diff
                    session.effective_seconds = time_diff
                
                with transaction.atomic():
                    if final_time > progress.current_time:
                        progress.current_time = final_time
                        progress.progress = min(
                            final_time / progress.total_duration if progress.total_duration > 0 else 0,
                            1.0
                        )
                        progress.version += 1
                        progress.save()
            
            session.end_session(final_time)
            
            return Response({
                'session_id': session_id,
                'status': 'ended',
                'end_time': session.end_time.isoformat(),
                'total_seconds': session.total_seconds,
                'effective_seconds': session.effective_seconds,
                'current_progress': {
                    'current_time': progress.current_time,
                    'progress': progress.progress
                }
            })
        except VideoWatchSession.DoesNotExist:
            return Response(
                {'error': '会话不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'], url_path='complete')
    def mark_complete(self, request):
        lesson_id = request.data.get('lesson_id')
        if not lesson_id:
            return Response(
                {'error': '请提供课时ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                progress = VideoProgress.objects.select_for_update().get(
                    lesson_id=lesson_id,
                    student=request.user
                )
                
                if progress.is_completed:
                    return Response({
                        **VideoProgressSerializer(progress).data,
                        'message': '课程已完成'
                    })
                
                progress.is_completed = True
                progress.completed_at = timezone.now()
                progress.progress = 1.0
                if progress.total_duration > 0:
                    progress.current_time = progress.total_duration
                progress.version += 1
                progress.save()
                
                self._update_course_progress(progress)
                
                return Response(VideoProgressSerializer(progress).data)
                
        except VideoProgress.DoesNotExist:
            return Response(
                {'error': '进度记录不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
    
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
        
        recent_sessions = VideoWatchSession.objects.filter(
            video_progress__student=request.user,
            start_time__gte=timezone.now() - timedelta(days=7)
        )
        
        daily_stats = {}
        for session in recent_sessions:
            date_key = session.start_time.date().isoformat()
            if date_key not in daily_stats:
                daily_stats[date_key] = {
                    'date': date_key,
                    'total_seconds': 0,
                    'session_count': 0
                }
            daily_stats[date_key]['total_seconds'] += session.total_seconds or 0
            daily_stats[date_key]['session_count'] += 1
        
        return Response({
            'total_watch_time_seconds': total_watch_time,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'completion_rate': completed_lessons / total_lessons if total_lessons > 0 else 0,
            'weekly_stats': list(daily_stats.values())
        })
    
    def _sync_single_item(self, request, item):
        request.data = item
        response = self.sync(request)
        return {
            'lesson_id': item.get('lesson_id'),
            'data': response.data if hasattr(response, 'data') else response,
            'success': True
        }
    
    def _manage_session(self, progress, session_id, current_time, is_playing, ip_address, user_agent, device_info):
        if session_id:
            try:
                session = VideoWatchSession.objects.get(
                    session_id=session_id,
                    video_progress=progress
                )
                session.update_heartbeat()
                
                if is_playing:
                    time_diff = current_time - session.initial_time
                    if time_diff > 0:
                        session.total_seconds = time_diff
                        session.save(update_fields=['total_seconds'])
            except VideoWatchSession.DoesNotExist:
                pass
        else:
            pass
    
    def _update_course_progress(self, progress):
        course = progress.lesson.chapter.course
        enrollment = CourseEnrollment.objects.filter(
            course=course,
            student=progress.student
        ).first()
        
        if enrollment:
            total_lessons = course.lessons.count()
            completed_lessons = VideoProgress.objects.filter(
                lesson__chapter__course=course,
                student=progress.student,
                is_completed=True
            ).count()
            
            enrollment.progress = completed_lessons / total_lessons if total_lessons > 0 else 0
            
            if enrollment.progress >= 1.0:
                enrollment.is_completed = True
                enrollment.completed_at = timezone.now()
            
            enrollment.save()
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def _parse_device_info(self, user_agent):
        if not user_agent:
            return 'unknown'
        
        user_agent_lower = user_agent.lower()
        
        device_type = 'desktop'
        if 'mobile' in user_agent_lower or 'android' in user_agent_lower:
            device_type = 'mobile'
        elif 'tablet' in user_agent_lower or 'ipad' in user_agent_lower:
            device_type = 'tablet'
        
        os_info = 'unknown'
        if 'windows' in user_agent_lower:
            os_info = 'windows'
        elif 'mac' in user_agent_lower:
            os_info = 'macos'
        elif 'linux' in user_agent_lower:
            os_info = 'linux'
        elif 'android' in user_agent_lower:
            os_info = 'android'
        elif 'iphone' in user_agent_lower or 'ipad' in user_agent_lower:
            os_info = 'ios'
        
        return f'{device_type}_{os_info}'


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


class VideoProgressConflictViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VideoProgressHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return VideoProgressConflict.objects.filter(
            video_progress__student=self.request.user
        )


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
