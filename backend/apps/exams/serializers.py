from rest_framework import serializers
from django.utils import timezone
from .models import (
    Exam, QuestionBank, ExamQuestion, ExamAttempt,
    ExamAnswer, CheatingRecord, ExamActivityLog
)
from apps.courses.serializers import CourseListSerializer, UserMiniSerializer


class QuestionBankSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionBank
        fields = [
            'id', 'course', 'chapter', 'teacher', 'question_text',
            'question_type', 'difficulty', 'options', 'correct_answer',
            'score', 'explanation', 'is_active', 'usage_count',
            'correct_rate', 'created_at'
        ]
        read_only_fields = ['usage_count', 'correct_rate']


class QuestionBankListSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionBank
        fields = [
            'id', 'question_text', 'question_type', 'difficulty',
            'score', 'is_active', 'usage_count', 'correct_rate'
        ]


class ExamQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamQuestion
        fields = [
            'id', 'exam', 'question_bank', 'question_text', 'question_type',
            'options', 'correct_answer', 'question_order', 'score', 'explanation'
        ]


class ExamQuestionStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamQuestion
        fields = [
            'id', 'question_text', 'question_type', 'options',
            'question_order', 'score'
        ]


class ExamListSerializer(serializers.ModelSerializer):
    course = CourseListSerializer(read_only=True)
    teacher = UserMiniSerializer(read_only=True)
    my_attempt_status = serializers.SerializerMethodField()
    my_attempt_score = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            'id', 'course', 'teacher', 'title', 'description', 'exam_type',
            'total_score', 'pass_score', 'total_questions', 'duration',
            'allow_enter_before', 'start_time', 'end_time', 'allow_late_enter',
            'late_enter_limit', 'status', 'show_score_immediately',
            'show_answers_after_exam', 'show_analysis', 'max_attempts',
            'auto_submit_on_timeout', 'is_shuffle_questions', 'is_shuffle_options',
            'is_question_pool', 'questions_per_student', 'enable_anti_cheating',
            'max_tab_switches', 'max_idle_time', 'require_fullscreen',
            'block_copy_paste', 'block_right_click', 'enable_face_verification',
            'verify_interval', 'password', 'my_attempt_status', 'my_attempt_score',
            'published_at', 'created_at'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'ip_whitelist': {'write_only': True},
        }

    def get_my_attempt_status(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            attempt = ExamAttempt.objects.filter(
                exam=obj,
                student=user
            ).order_by('-attempt_number').first()
            if attempt:
                return attempt.status
        return 'not_started'

    def get_my_attempt_score(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            attempt = ExamAttempt.objects.filter(
                exam=obj,
                student=user,
                status='graded'
            ).order_by('-attempt_number').first()
            if attempt and obj.show_score_immediately:
                return str(attempt.total_score) if attempt.total_score else None
        return None


class ExamDetailSerializer(ExamListSerializer):
    questions = serializers.SerializerMethodField()

    class Meta(ExamListSerializer.Meta):
        fields = ExamListSerializer.Meta.fields + ['questions']

    def get_questions(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and (
            user.role in ['teacher', 'admin'] or 
            user.is_superuser or
            obj.teacher == user
        ):
            return ExamQuestionSerializer(obj.exam_questions.all(), many=True).data
        
        attempt = ExamAttempt.objects.filter(
            exam=obj,
            student=user,
            status='in_progress'
        ).first()
        
        if attempt:
            questions = obj.exam_questions.all()
            if obj.is_shuffle_questions:
                shuffled_ids = attempt.shuffled_questions
                if shuffled_ids:
                    id_order = {qid: idx for idx, qid in enumerate(shuffled_ids)}
                    questions = sorted(questions, key=lambda q: id_order.get(q.id, 9999))
            
            return ExamQuestionStudentSerializer(questions, many=True).data
        
        return []


class ExamCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = [
            'course', 'title', 'description', 'exam_type', 'total_score',
            'pass_score', 'duration', 'allow_enter_before', 'start_time',
            'end_time', 'allow_late_enter', 'late_enter_limit', 'status',
            'show_score_immediately', 'show_answers_after_exam', 'show_analysis',
            'max_attempts', 'auto_submit_on_timeout', 'is_shuffle_questions',
            'is_shuffle_options', 'is_question_pool', 'questions_per_student',
            'enable_anti_cheating', 'max_tab_switches', 'max_idle_time',
            'require_fullscreen', 'block_copy_paste', 'block_right_click',
            'enable_face_verification', 'verify_interval', 'password'
        ]

    def validate(self, data):
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        duration = data.get('duration')
        
        if start_time and end_time:
            if start_time >= end_time:
                raise serializers.ValidationError('开始时间必须早于结束时间')
            
            actual_duration = int((end_time - start_time).total_seconds() / 60)
            if duration and actual_duration != duration:
                pass
        
        total_score = data.get('total_score', 100)
        pass_score = data.get('pass_score', 60)
        if pass_score > total_score:
            raise serializers.ValidationError('及格分数不能大于总分')
        
        return data

    def create(self, validated_data):
        validated_data['teacher'] = self.context['request'].user
        if validated_data.get('status') == 'published':
            validated_data['published_at'] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        old_status = instance.status
        new_status = validated_data.get('status')
        
        if new_status == 'published' and old_status != 'published':
            validated_data['published_at'] = timezone.now()
        
        return super().update(instance, validated_data)


class ExamAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamAnswer
        fields = [
            'id', 'attempt', 'question', 'answer_text', 'answer_choice',
            'answer_file', 'is_answered', 'is_skipped', 'is_flagged',
            'is_correct', 'score', 'partial_score', 'teacher_feedback',
            'time_spent', 'created_at'
        ]


class ExamAnswerSubmitSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(required=True)
    answer_text = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    answer_choice = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )
    is_skipped = serializers.BooleanField(default=False, required=False)
    is_flagged = serializers.BooleanField(default=False, required=False)
    time_spent = serializers.IntegerField(required=False, allow_null=True, min_value=0)


class ExamAnswerBatchSubmitSerializer(serializers.Serializer):
    request_id = serializers.CharField(required=False, allow_blank=True, max_length=100)
    answers = ExamAnswerSubmitSerializer(many=True, required=True)


class ExamAttemptSerializer(serializers.ModelSerializer):
    exam = ExamListSerializer(read_only=True)
    student = UserMiniSerializer(read_only=True)
    graded_by = UserMiniSerializer(read_only=True)
    answers = ExamAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = ExamAttempt
        fields = [
            'id', 'exam', 'student', 'attempt_number', 'start_time',
            'submit_time', 'end_time', 'time_spent', 'total_score',
            'score_percentage', 'is_passed', 'correct_count', 'incorrect_count',
            'unanswered_count', 'status', 'is_cheating_detected', 'cheating_reason',
            'submitted_manually', 'auto_submit_reason', 'answers',
            'ip_address', 'device_info', 'created_at'
        ]


class ExamActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamActivityLog
        fields = [
            'id', 'attempt', 'activity_type', 'details', 'timestamp'
        ]


class CheatingRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheatingRecord
        fields = [
            'id', 'attempt', 'cheating_type', 'description', 'severity',
            'evidence', 'action_taken', 'is_verified', 'verified_by',
            'verified_at', 'created_at'
        ]


class AntiCheatingEventSerializer(serializers.Serializer):
    attempt_id = serializers.IntegerField(required=True)
    event_type = serializers.CharField(required=True)
    details = serializers.DictField(required=False, default=dict)
    timestamp = serializers.DateTimeField(required=False, default=None)


class ExamStartSerializer(serializers.Serializer):
    exam_id = serializers.IntegerField(required=True)
    password = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    request_id = serializers.CharField(required=False, allow_blank=True, max_length=100)


class ExamGradeItemSerializer(serializers.Serializer):
    attempt_id = serializers.IntegerField(required=True)
    total_score = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=True, min_value=0
    )
    feedback = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    question_scores = serializers.DictField(
        child=serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0),
        required=False,
        allow_empty=True
    )


class ExamBatchGradeSerializer(serializers.Serializer):
    request_id = serializers.CharField(required=False, allow_blank=True, max_length=100)
    grades = ExamGradeItemSerializer(many=True, required=True)


class ExamSubmitSerializer(serializers.Serializer):
    request_id = serializers.CharField(required=False, allow_blank=True, max_length=100)
    answers = ExamAnswerSubmitSerializer(many=True, required=False)
