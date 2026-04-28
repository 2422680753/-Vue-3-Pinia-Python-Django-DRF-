from rest_framework import serializers
from .models import (
    VideoProgress, VideoProgressHistory, VideoSource, 
    VideoSubtitle, WatchList, WatchListItem
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
            'created_at'
        ]


class VideoProgressSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    course_title = serializers.CharField(source='lesson.chapter.course.title', read_only=True)
    course_id = serializers.IntegerField(source='lesson.chapter.course.id', read_only=True)
    chapter_id = serializers.IntegerField(source='lesson.chapter.id', read_only=True)
    lesson_id = serializers.IntegerField(source='lesson.id', read_only=True)

    class Meta:
        model = VideoProgress
        fields = [
            'id', 'lesson', 'lesson_id', 'lesson_title', 'course_id', 'course_title',
            'chapter_id', 'current_time', 'total_duration', 'play_count',
            'watch_duration', 'progress', 'is_completed', 'completed_at',
            'last_watched_at', 'created_at'
        ]


class VideoProgressCreateSerializer(serializers.Serializer):
    lesson_id = serializers.IntegerField(required=True)
    current_time = serializers.FloatField(required=True)
    total_duration = serializers.FloatField(required=True)
    playback_rate = serializers.FloatField(default=1.0)
    is_seeked = serializers.BooleanField(default=False)
    seek_from = serializers.FloatField(null=True)
    seek_to = serializers.FloatField(null=True)
    is_playing = serializers.BooleanField(default=True)


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
