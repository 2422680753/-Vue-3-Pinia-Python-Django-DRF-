from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Category, Tag, Course, Chapter, Lesson,
    CourseEnrollment, CourseReview, LiveCourse, LiveChatMessage
)

User = get_user_model()


class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'real_name', 'avatar']


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    course_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'parent', 'icon', 'sort_order', 'is_active', 'children', 'course_count']

    def get_children(self, obj):
        if obj.children.exists():
            return CategorySerializer(obj.children.all(), many=True).data
        return []

    def get_course_count(self, obj):
        return obj.courses.filter(status='published').count()


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color']


class LessonSerializer(serializers.ModelSerializer):
    is_watched = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'chapter', 'title', 'description', 'lesson_order',
            'duration', 'video_url', 'external_video_id', 'video_provider',
            'is_free', 'is_locked', 'requires_completion',
            'attachments', 'notes', 'is_watched', 'progress'
        ]

    def get_is_watched(self, obj):
        from apps.videos.models import VideoProgress
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            return VideoProgress.objects.filter(lesson=obj, student=user, is_completed=True).exists()
        return False

    def get_progress(self, obj):
        from apps.videos.models import VideoProgress
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            progress = VideoProgress.objects.filter(lesson=obj, student=user).first()
            if progress:
                return progress.progress
        return 0


class ChapterSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)
    lesson_count = serializers.SerializerMethodField()
    completed_count = serializers.SerializerMethodField()

    class Meta:
        model = Chapter
        fields = [
            'id', 'course', 'title', 'description', 'chapter_order',
            'duration', 'is_locked', 'lessons', 'lesson_count', 'completed_count'
        ]

    def get_lesson_count(self, obj):
        return obj.lessons.count()

    def get_completed_count(self, obj):
        from apps.videos.models import VideoProgress
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            return VideoProgress.objects.filter(
                lesson__chapter=obj,
                student=user,
                is_completed=True
            ).count()
        return 0


class CourseListSerializer(serializers.ModelSerializer):
    instructor = UserMiniSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    is_enrolled = serializers.SerializerMethodField()
    enrollment_progress = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'short_description', 'description',
            'instructor', 'category', 'tags', 'course_type', 'level',
            'cover_image', 'preview_video', 'price', 'original_price',
            'duration', 'total_lessons', 'total_students', 'status',
            'is_featured', 'is_free', 'average_rating', 'review_count',
            'is_enrolled', 'enrollment_progress', 'published_at', 'created_at'
        ]

    def get_is_enrolled(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            return CourseEnrollment.objects.filter(course=obj, student=user, is_active=True).exists()
        return False

    def get_enrollment_progress(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            enrollment = CourseEnrollment.objects.filter(course=obj, student=user, is_active=True).first()
            if enrollment:
                return enrollment.progress
        return 0


class CourseDetailSerializer(serializers.ModelSerializer):
    instructor = UserMiniSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    chapters = ChapterSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    is_enrolled = serializers.SerializerMethodField()
    enrollment_progress = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'short_description', 'description',
            'instructor', 'category', 'tags', 'course_type', 'level',
            'cover_image', 'preview_video', 'price', 'original_price',
            'duration', 'total_lessons', 'total_students', 'status',
            'is_featured', 'is_free', 'requirements', 'target_audience',
            'objectives', 'average_rating', 'review_count', 'chapters',
            'is_enrolled', 'enrollment_progress', 'discount_percent',
            'published_at', 'created_at', 'updated_at'
        ]

    def get_is_enrolled(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            return CourseEnrollment.objects.filter(course=obj, student=user, is_active=True).exists()
        return False

    def get_enrollment_progress(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            enrollment = CourseEnrollment.objects.filter(course=obj, student=user, is_active=True).first()
            if enrollment:
                return enrollment.progress
        return 0

    def get_discount_percent(self, obj):
        return obj.get_discount_percent()


class CourseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            'title', 'slug', 'short_description', 'description',
            'category', 'tags', 'course_type', 'level',
            'cover_image', 'preview_video', 'price', 'original_price',
            'is_free', 'requirements', 'target_audience', 'objectives',
            'status'
        ]

    def create(self, validated_data):
        validated_data['instructor'] = self.context['request'].user
        tags = validated_data.pop('tags', [])
        course = super().create(validated_data)
        course.tags.set(tags)
        return course


class ChapterCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapter
        fields = ['title', 'description', 'chapter_order', 'is_locked']


class LessonCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = [
            'chapter', 'title', 'description', 'lesson_order',
            'duration', 'video_url', 'external_video_id', 'video_provider',
            'is_free', 'is_locked', 'requires_completion', 'attachments', 'notes'
        ]


class CourseEnrollmentSerializer(serializers.ModelSerializer):
    course = CourseListSerializer(read_only=True)
    student = UserMiniSerializer(read_only=True)

    class Meta:
        model = CourseEnrollment
        fields = [
            'id', 'course', 'student', 'enrollment_type', 'price_paid',
            'progress', 'is_active', 'is_completed', 'completed_at',
            'last_accessed_at', 'enrolled_at'
        ]


class CourseReviewSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = CourseReview
        fields = [
            'id', 'course', 'course_title', 'student', 'rating',
            'content', 'is_anonymous', 'likes_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['likes_count']


class CourseReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseReview
        fields = ['rating', 'content', 'is_anonymous']

    def validate(self, attrs):
        user = self.context['request'].user
        course = self.context.get('course')
        
        if course and not CourseEnrollment.objects.filter(
            course=course, student=user, is_active=True
        ).exists():
            raise serializers.ValidationError("您需要先报名该课程才能评价")
        
        if course and CourseReview.objects.filter(course=course, student=user).exists():
            raise serializers.ValidationError("您已经评价过该课程")
        
        return attrs

    def create(self, validated_data):
        validated_data['student'] = self.context['request'].user
        validated_data['course'] = self.context.get('course')
        return super().create(validated_data)


class LiveCourseSerializer(serializers.ModelSerializer):
    course = CourseListSerializer(read_only=True)
    instructor = UserMiniSerializer(read_only=True)

    class Meta:
        model = LiveCourse
        fields = [
            'id', 'course', 'instructor', 'start_time', 'end_time',
            'stream_url', 'playback_url', 'max_viewers',
            'current_viewers', 'total_viewers', 'status',
            'is_interactive', 'has_recording', 'created_at'
        ]


class LiveChatMessageSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)

    class Meta:
        model = LiveChatMessage
        fields = [
            'id', 'live_course', 'user', 'content', 'message_type',
            'is_answered', 'created_at'
        ]
