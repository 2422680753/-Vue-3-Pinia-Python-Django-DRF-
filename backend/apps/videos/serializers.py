from rest_framework import serializers
from .models import (
    VideoProgress, VideoProgressHistory, VideoProgressConflict,
    VideoWatchSession, VideoSource, VideoSubtitle, WatchList, WatchListItem
)
from apps.courses.serializers import LessonSerializer, CourseListSerializer, UserMiniSerializer


class VideoSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoSource
        fields = [
            'id', 'lesson', 'quality', 'video_url', 'file_size',
            'bitrate', 'resolution', 'is_encrypted', 'drm_provider',
            'is_active'
        ]


class VideoSubtitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoSubtitle
        fields = [
            'id', 'lesson', 'language', 'subtitle_file', 'label',
            'is_default', 'is_active'
        ]


class VideoProgressHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoProgressHistory
        fields = [
            'id', 'video_progress', 'from_time', 'to_time', 'duration',
            'playback_rate', 'is_seeked', 'seek_from', 'seek_to',
            'session_id', 'request_id', 'ip_address', 'device_info',
            'created_at'
        ]


class VideoProgressConflictSerializer(serializers.ModelSerializer):
    conflict_type_display = serializers.CharField(source='get_conflict_type_display', read_only=True)
    
    class Meta:
        model = VideoProgressConflict
        fields = [
            'id', 'video_progress', 'conflict_type', 'conflict_type_display',
            'server_state', 'client_state', 'resolution', 'is_resolved',
            'session_id', 'ip_address', 'device_info',
            'created_at', 'resolved_at'
        ]


class VideoWatchSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoWatchSession
        fields = [
            'id', 'video_progress', 'session_id',
            'start_time', 'end_time', 'initial_time', 'final_time',
            'total_seconds', 'effective_seconds',
            'is_active', 'last_heartbeat',
            'ip_address', 'device_info', 'user_agent',
            'created_at'
        ]


class VideoProgressSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    course_title = serializers.CharField(source='lesson.chapter.course.title', read_only=True)
    course_id = serializers.IntegerField(source='lesson.chapter.course.id', read_only=True)
    chapter_id = serializers.IntegerField(source='lesson.chapter.id', read_only=True)
    lesson_id = serializers.IntegerField(source='lesson.id', read_only=True)
    
    watch_sessions = VideoWatchSessionSerializer(many=True, read_only=True)
    
    class Meta:
        model = VideoProgress
        fields = [
            'id', 'lesson', 'lesson_id', 'lesson_title', 'course_id', 'course_title',
            'chapter_id', 'current_time', 'total_duration', 'play_count',
            'watch_duration', 'progress', 'is_completed', 'completed_at',
            'last_watched_at', 'created_at',
            'version', 'last_update_time', 'last_update_client', 'last_update_ip',
            'watch_sessions'
        ]


class VideoProgressSyncSerializer(serializers.Serializer):
    lesson_id = serializers.IntegerField(required=True)
    current_time = serializers.FloatField(required=True, min_value=0)
    total_duration = serializers.FloatField(required=True, min_value=0)
    playback_rate = serializers.FloatField(default=1.0, min_value=0.25, max_value=3.0)
    is_seeked = serializers.BooleanField(default=False)
    seek_from = serializers.FloatField(required=False, min_value=0, allow_null=True)
    seek_to = serializers.FloatField(required=False, min_value=0, allow_null=True)
    is_playing = serializers.BooleanField(default=True)
    request_id = serializers.CharField(required=False, max_length=64, allow_null=True, allow_blank=True)
    client_version = serializers.IntegerField(required=False, min_value=1, allow_null=True)
    session_id = serializers.CharField(required=False, max_length=100, allow_null=True, allow_blank=True)
    client_timestamp = serializers.DateTimeField(required=False, allow_null=True)
    
    def validate(self, data):
        current_time = data.get('current_time', 0)
        total_duration = data.get('total_duration', 0)
        
        if total_duration > 0 and current_time > total_duration + 60:
            raise serializers.ValidationError({
                'current_time': '当前播放时间不能超过视频时长 + 60秒'
            })
        
        return data


class VideoProgressBatchSyncItemSerializer(serializers.Serializer):
    lesson_id = serializers.IntegerField(required=True)
    current_time = serializers.FloatField(required=True, min_value=0)
    total_duration = serializers.FloatField(required=True, min_value=0)
    playback_rate = serializers.FloatField(default=1.0)
    is_seeked = serializers.BooleanField(default=False)
    seek_from = serializers.FloatField(required=False, allow_null=True)
    seek_to = serializers.FloatField(required=False, allow_null=True)
    is_playing = serializers.BooleanField(default=True)
    request_id = serializers.CharField(required=False, max_length=64)
    client_version = serializers.IntegerField(required=False)
    session_id = serializers.CharField(required=False, max_length=100)


class VideoProgressBatchSerializer(serializers.Serializer):
    items = VideoProgressBatchSyncItemSerializer(many=True, required=True)
    batch_id = serializers.CharField(required=False, max_length=64)
    
    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('批量同步项不能为空')
        
        if len(value) > 100:
            raise serializers.ValidationError('批量同步项不能超过100条')
        
        return value


class WatchListItemSerializer(serializers.ModelSerializer):
    lesson = LessonSerializer(read_only=True)
    lesson_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = WatchListItem
        fields = ['id', 'watch_list', 'lesson', 'lesson_id', 'item_order', 'added_at']


class WatchListSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)
    items = WatchListItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = WatchList
        fields = [
            'id', 'student', 'name', 'description', 'is_public',
            'is_default', 'items', 'item_count', 'created_at', 'updated_at'
        ]

    def get_item_count(self, obj):
        return obj.items.count()


class WatchListCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WatchList
        fields = ['name', 'description', 'is_public']
