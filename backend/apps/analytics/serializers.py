from rest_framework import serializers
from .models import (
    LearningSession, DailyLearningStats, CourseProgressStats,
    LearningBehavior, LearningAnalytics, ClassAnalytics
)
from apps.courses.serializers import CourseListSerializer, UserMiniSerializer, LessonListSerializer


class LearningSessionSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)
    course = CourseListSerializer(read_only=True)
    lesson = LessonListSerializer(read_only=True)

    class Meta:
        model = LearningSession
        fields = [
            'id', 'student', 'course', 'lesson', 'session_type',
            'start_time', 'end_time', 'duration', 'effective_duration',
            'is_active', 'device_info', 'ip_address', 'location',
            'interactions', 'focus_intervals', 'distraction_events',
            'focus_score', 'efficiency_score', 'created_at'
        ]
        read_only_fields = ['created_at']


class DailyLearningStatsSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)

    class Meta:
        model = DailyLearningStats
        fields = [
            'id', 'student', 'date', 'total_sessions', 'total_duration',
            'effective_duration', 'courses_visited', 'lessons_completed',
            'assignments_submitted', 'assignments_graded', 'exams_taken',
            'exams_passed', 'average_focus_score', 'average_efficiency_score',
            'streak_days', 'is_learning_day', 'created_at'
        ]


class CourseProgressStatsSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)
    course = CourseListSerializer(read_only=True)

    class Meta:
        model = CourseProgressStats
        fields = [
            'id', 'student', 'course', 'overall_progress',
            'total_lessons', 'completed_lessons', 'in_progress_lessons',
            'total_video_duration', 'watched_video_duration',
            'total_assignments', 'submitted_assignments', 'graded_assignments',
            'assignments_average_score', 'total_exams', 'taken_exams',
            'passed_exams', 'exams_average_score',
            'first_access_at', 'last_access_at', 'total_study_time',
            'estimated_remaining_time', 'learning_speed_score',
            'mastery_score', 'predicted_completion_date', 'created_at'
        ]


class LearningBehaviorSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)
    course = CourseListSerializer(read_only=True)
    lesson = LessonListSerializer(read_only=True)

    class Meta:
        model = LearningBehavior
        fields = [
            'id', 'student', 'course', 'lesson', 'behavior_type',
            'details', 'timestamp', 'session_id', 'created_at'
        ]


class LearningAnalyticsSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)
    course = CourseListSerializer(read_only=True)

    class Meta:
        model = LearningAnalytics
        fields = [
            'id', 'student', 'course', 'analysis_date',
            'overall_engagement_score', 'video_watching_pattern',
            'video_completion_rate', 'average_playback_speed',
            'seek_frequency', 'assignment_submission_pattern',
            'assignment_on_time_rate', 'assignment_avg_score',
            'exam_performance', 'exam_avg_score', 'exam_pass_rate',
            'learning_time_distribution', 'peak_learning_hours',
            'weekly_learning_pattern', 'focus_analysis',
            'average_focus_score', 'distraction_events_count',
            'predictions', 'predicted_final_score',
            'completion_probability', 'dropout_risk',
            'strengths', 'weaknesses', 'recommendations',
            'created_at'
        ]


class ClassAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassAnalytics
        fields = [
            'id', 'class_obj', 'analysis_date', 'total_students',
            'active_students', 'at_risk_students', 'average_attendance_rate',
            'average_progress', 'assignment_submission_rate',
            'assignment_average_score', 'exam_average_score',
            'exam_pass_rate', 'weekly_activity_trend', 'score_distribution',
            'progress_distribution', 'top_performers', 'struggling_students',
            'class_engagement_score', 'learning_efficiency_index',
            'insights', 'recommendations', 'created_at'
        ]


class LearningSessionStartSerializer(serializers.Serializer):
    course_id = serializers.IntegerField(required=True)
    lesson_id = serializers.IntegerField(required=False, allow_null=True)
    session_type = serializers.ChoiceField(
        choices=['video', 'reading', 'assignment', 'exam', 'live', 'other'],
        default='video'
    )


class LearningSessionUpdateSerializer(serializers.Serializer):
    focus_score = serializers.FloatField(required=False, min_value=0, max_value=1)
    efficiency_score = serializers.FloatField(required=False, min_value=0, max_value=1)
    interactions = serializers.ListField(required=False, default=list)
    focus_intervals = serializers.ListField(required=False, default=list)
    distraction_events = serializers.ListField(required=False, default=list)


class LearningBehaviorCreateSerializer(serializers.Serializer):
    course_id = serializers.IntegerField(required=True)
    lesson_id = serializers.IntegerField(required=False, allow_null=True)
    behavior_type = serializers.CharField(required=True)
    details = serializers.DictField(required=False, default=dict)
    session_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
