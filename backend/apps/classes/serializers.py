from rest_framework import serializers
from .models import (
    Class, ClassStudent, ClassSchedule, ClassAttendance,
    ClassAnnouncement, ClassMaterial, ClassStatus
)
from apps.courses.serializers import CourseListSerializer, UserMiniSerializer


class ClassStudentSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)
    class_obj_name = serializers.CharField(source='class_obj.name', read_only=True)

    class Meta:
        model = ClassStudent
        fields = [
            'id', 'class_obj', 'class_obj_name', 'student', 'join_type',
            'is_active', 'dropped_at', 'drop_reason', 'final_grade',
            'attendance_rate', 'is_graduated', 'graduated_at', 'notes',
            'enrolled_at', 'created_at'
        ]
        read_only_fields = ['enrolled_at', 'created_at']


class ClassStudentListSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)

    class Meta:
        model = ClassStudent
        fields = [
            'id', 'student', 'join_type', 'is_active', 'final_grade',
            'attendance_rate', 'is_graduated', 'enrolled_at'
        ]


class ClassScheduleSerializer(serializers.ModelSerializer):
    teacher = UserMiniSerializer(read_only=True)
    class_obj_name = serializers.CharField(source='class_obj.name', read_only=True)

    class Meta:
        model = ClassSchedule
        fields = [
            'id', 'class_obj', 'class_obj_name', 'title', 'description',
            'day_of_week', 'start_time', 'end_time', 'start_date', 'end_date',
            'is_recurring', 'repeat_weeks', 'location', 'meeting_url',
            'teacher', 'lesson', 'is_active', 'created_at'
        ]
        read_only_fields = ['created_at']


class ClassAttendanceSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)
    marked_by = UserMiniSerializer(read_only=True)
    schedule_title = serializers.CharField(source='schedule.title', read_only=True)

    class Meta:
        model = ClassAttendance
        fields = [
            'id', 'schedule', 'schedule_title', 'student', 'attendance_date',
            'status', 'check_in_time', 'check_out_time', 'notes',
            'marked_by', 'created_at'
        ]
        read_only_fields = ['created_at', 'marked_by']


class ClassAttendanceBulkSerializer(serializers.Serializer):
    schedule_id = serializers.IntegerField(required=True)
    attendance_date = serializers.DateField(required=True)
    records = serializers.ListField(
        child=serializers.DictField(),
        required=True
    )


class ClassAnnouncementSerializer(serializers.ModelSerializer):
    teacher = UserMiniSerializer(read_only=True)
    class_obj_name = serializers.CharField(source='class_obj.name', read_only=True)

    class Meta:
        model = ClassAnnouncement
        fields = [
            'id', 'class_obj', 'class_obj_name', 'teacher', 'title', 'content',
            'priority', 'is_pinned', 'attachments', 'publish_at', 'expire_at',
            'read_count', 'is_draft', 'created_at'
        ]
        read_only_fields = ['read_count', 'created_at']


class ClassMaterialSerializer(serializers.ModelSerializer):
    teacher = UserMiniSerializer(read_only=True)
    class_obj_name = serializers.CharField(source='class_obj.name', read_only=True)

    class Meta:
        model = ClassMaterial
        fields = [
            'id', 'class_obj', 'class_obj_name', 'teacher', 'title', 'description',
            'file', 'file_type', 'file_size', 'download_count', 'view_count',
            'is_free', 'is_locked', 'category', 'created_at'
        ]
        read_only_fields = ['file_type', 'file_size', 'download_count', 'view_count', 'created_at']


class ClassListSerializer(serializers.ModelSerializer):
    course = CourseListSerializer(read_only=True)
    teacher = UserMiniSerializer(read_only=True)
    assistant_teachers = UserMiniSerializer(many=True, read_only=True)
    student_count = serializers.SerializerMethodField()
    schedule_count = serializers.SerializerMethodField()
    announcement_count = serializers.SerializerMethodField()

    class Meta:
        model = Class
        fields = [
            'id', 'name', 'code', 'description', 'course', 'teacher',
            'assistant_teachers', 'max_students', 'current_students',
            'start_date', 'end_date', 'status', 'is_private', 'join_code',
            'student_count', 'schedule_count', 'announcement_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['code', 'join_code', 'current_students', 'created_at', 'updated_at']

    def get_student_count(self, obj):
        return obj.students.filter(is_active=True).count()

    def get_schedule_count(self, obj):
        return obj.schedules.filter(is_active=True).count()

    def get_announcement_count(self, obj):
        return obj.announcements.filter(is_draft=False).count()


class ClassDetailSerializer(ClassListSerializer):
    students = serializers.SerializerMethodField()
    schedules = ClassScheduleSerializer(many=True, read_only=True, source='schedules.all')
    recent_announcements = serializers.SerializerMethodField()

    class Meta(ClassListSerializer.Meta):
        fields = ClassListSerializer.Meta.fields + [
            'schedule', 'students', 'schedules', 'recent_announcements'
        ]

    def get_students(self, obj):
        active_students = obj.students.filter(is_active=True)[:50]
        return ClassStudentListSerializer(active_students, many=True).data

    def get_recent_announcements(self, obj):
        announcements = obj.announcements.filter(is_draft=False)[:10]
        return ClassAnnouncementSerializer(announcements, many=True).data


class ClassCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Class
        fields = [
            'name', 'description', 'course', 'assistant_teachers',
            'max_students', 'start_date', 'end_date', 'schedule',
            'is_private'
        ]

    def create(self, validated_data):
        validated_data['teacher'] = self.context['request'].user
        return super().create(validated_data)


class ClassGradeSerializer(serializers.Serializer):
    student_id = serializers.IntegerField(required=True)
    final_grade = serializers.DecimalField(max_digits=5, decimal_places=2, required=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ClassGraduateSerializer(serializers.Serializer):
    student_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True
    )
    final_grade = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class JoinClassSerializer(serializers.Serializer):
    join_code = serializers.CharField(max_length=8, required=True)
