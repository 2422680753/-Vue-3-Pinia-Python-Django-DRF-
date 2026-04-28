import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from apps.videos.models import VideoProgress, VideoProgressHistory
from apps.courses.models import Lesson, CourseEnrollment


class VideoProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close(code=401)
            return
        
        self.lesson_id = self.scope['url_route']['kwargs']['lesson_id']
        
        has_access = await self.check_lesson_access(self.lesson_id, self.user)
        if not has_access:
            await self.close(code=403)
            return
        
        self.group_name = f'video_progress_{self.lesson_id}_{self.user.id}'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        current_progress = await self.get_current_progress(self.lesson_id, self.user)
        if current_progress:
            await self.send(text_data=json.dumps({
                'type': 'progress_sync',
                'data': {
                    'lesson_id': self.lesson_id,
                    'current_time': current_progress.current_time,
                    'total_duration': current_progress.total_duration,
                    'progress': current_progress.progress,
                    'is_completed': current_progress.is_completed,
                    'play_count': current_progress.play_count
                }
            }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'progress_update':
                await self.handle_progress_update(data.get('data'))
            elif message_type == 'playback_event':
                await self.handle_playback_event(data.get('data'))
            elif message_type == 'heartbeat':
                await self.handle_heartbeat()
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))

    async def handle_progress_update(self, data):
        if not data:
            return
        
        lesson_id = data.get('lesson_id')
        current_time = data.get('current_time')
        total_duration = data.get('total_duration')
        playback_rate = data.get('playback_rate', 1.0)
        is_seeked = data.get('is_seeked', False)
        seek_from = data.get('seek_from')
        seek_to = data.get('seek_to')
        is_playing = data.get('is_playing', True)
        
        progress, is_complete = await self.update_progress(
            lesson_id=lesson_id,
            user=self.user,
            current_time=current_time,
            total_duration=total_duration,
            playback_rate=playback_rate,
            is_seeked=is_seeked,
            seek_from=seek_from,
            seek_to=seek_to,
            is_playing=is_playing
        )
        
        await self.send(text_data=json.dumps({
            'type': 'progress_ack',
            'data': {
                'lesson_id': lesson_id,
                'current_time': progress.current_time,
                'progress': progress.progress,
                'is_completed': progress.is_completed,
                'server_time': timezone.now().isoformat()
            }
        }))
        
        if is_complete and not progress.is_completed:
            await self.mark_as_complete(progress)
            await self.send(text_data=json.dumps({
                'type': 'lesson_complete',
                'data': {
                    'lesson_id': lesson_id,
                    'message': '恭喜！您已完成本课时学习'
                }
            }))

    async def handle_playback_event(self, data):
        if not data:
            return
        
        event_type = data.get('event')
        lesson_id = data.get('lesson_id')
        current_time = data.get('current_time')
        
        await self.record_playback_event(
            user=self.user,
            lesson_id=lesson_id,
            event_type=event_type,
            current_time=current_time
        )
        
        await self.send(text_data=json.dumps({
            'type': 'event_ack',
            'data': {'event': event_type, 'received': True}
        }))

    async def handle_heartbeat(self):
        await self.send(text_data=json.dumps({
            'type': 'heartbeat_ack',
            'data': {'server_time': timezone.now().isoformat()}
        }))

    @database_sync_to_async
    def check_lesson_access(self, lesson_id, user):
        try:
            lesson = Lesson.objects.select_related('chapter__course').get(id=lesson_id)
        except Lesson.DoesNotExist:
            return False
        
        if lesson.is_free:
            return True
        
        if user.role in ['teacher', 'admin'] or user.is_superuser:
            return True
        
        return CourseEnrollment.objects.filter(
            course=lesson.chapter.course,
            student=user,
            is_active=True
        ).exists()

    @database_sync_to_async
    def get_current_progress(self, lesson_id, user):
        try:
            return VideoProgress.objects.get(lesson_id=lesson_id, student=user)
        except VideoProgress.DoesNotExist:
            return None

    @database_sync_to_async
    def update_progress(self, lesson_id, user, current_time, total_duration, 
                        playback_rate=1.0, is_seeked=False, seek_from=None, seek_to=None,
                        is_playing=True):
        progress, created = VideoProgress.objects.get_or_create(
            lesson_id=lesson_id,
            student=user,
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
            
            if is_playing and progress.current_time == 0:
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
        
        return progress, is_complete

    @database_sync_to_async
    def mark_as_complete(self, progress):
        progress.is_completed = True
        progress.completed_at = timezone.now()
        progress.save()
        
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

    @database_sync_to_async
    def record_playback_event(self, user, lesson_id, event_type, current_time):
        try:
            progress = VideoProgress.objects.get(lesson_id=lesson_id, student=user)
            
            if event_type == 'play':
                progress.play_count += 1
                progress.save()
        except VideoProgress.DoesNotExist:
            pass
