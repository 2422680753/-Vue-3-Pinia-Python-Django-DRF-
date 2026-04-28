from rest_framework import serializers
from .models import (
    Assignment, AssignmentQuestion, GradingRubric,
    AssignmentSubmission, SubmissionFile, AnswerResponse,
    GradingComment, SubmissionVersion
)
from apps.courses.serializers import CourseListSerializer, UserMiniSerializer, LessonSerializer


class GradingRubricSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradingRubric
        fields = [
            'id', 'assignment', 'question', 'criterion', 'description',
            'max_score', 'levels', 'rubric_order'
        ]


class AssignmentQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentQuestion
        fields = [
            'id', 'assignment', 'question_text', 'question_type',
            'question_order', 'score', 'choices', 'correct_answer',
            'is_auto_graded', 'explanation'
        ]


class AssignmentQuestionStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentQuestion
        fields = [
            'id', 'question_text', 'question_type', 'question_order',
            'score', 'choices'
        ]


class AssignmentListSerializer(serializers.ModelSerializer):
    course = CourseListSerializer(read_only=True)
    teacher = UserMiniSerializer(read_only=True)
    lesson = LessonSerializer(read_only=True)
    my_submission_status = serializers.SerializerMethodField()
    my_submission_score = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            'id', 'course', 'lesson', 'teacher', 'title', 'description',
            'assignment_type', 'total_score', 'pass_score',
            'allows_file_upload', 'allowed_file_types', 'max_file_size',
            'max_file_count', 'allows_text_answer', 'text_answer_required',
            'start_time', 'deadline', 'late_deadline', 'allow_late_submission',
            'late_submission_penalty', 'allow_resubmission', 'max_resubmissions',
            'status', 'published_at', 'my_submission_status', 'my_submission_score',
            'created_at'
        ]

    def get_my_submission_status(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            submission = AssignmentSubmission.objects.filter(
                assignment=obj,
                student=user
            ).first()
            if submission:
                return submission.submission_status
        return 'not_submitted'

    def get_my_submission_score(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            submission = AssignmentSubmission.objects.filter(
                assignment=obj,
                student=user
            ).first()
            if submission:
                return str(submission.final_score) if submission.final_score else None
        return None


class AssignmentDetailSerializer(AssignmentListSerializer):
    questions = serializers.SerializerMethodField()
    rubrics = GradingRubricSerializer(many=True, read_only=True)

    class Meta(AssignmentListSerializer.Meta):
        fields = AssignmentListSerializer.Meta.fields + ['questions', 'rubrics']

    def get_questions(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and (
            user.role in ['teacher', 'admin'] or 
            user.is_superuser or
            obj.teacher == user
        ):
            return AssignmentQuestionSerializer(obj.questions.all(), many=True).data
        return AssignmentQuestionStudentSerializer(obj.questions.all(), many=True).data


class AssignmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = [
            'course', 'lesson', 'title', 'description', 'assignment_type',
            'total_score', 'pass_score', 'allows_file_upload', 'allowed_file_types',
            'max_file_size', 'max_file_count', 'allows_text_answer',
            'text_answer_required', 'start_time', 'deadline', 'late_deadline',
            'allow_late_submission', 'late_submission_penalty',
            'allow_resubmission', 'max_resubmissions', 'status'
        ]

    def create(self, validated_data):
        validated_data['teacher'] = self.context['request'].user
        return super().create(validated_data)


class SubmissionFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionFile
        fields = ['id', 'submission', 'file', 'filename', 'file_size', 'file_type', 'created_at']


class AnswerResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerResponse
        fields = [
            'id', 'submission', 'question', 'answer_text', 'answer_choice',
            'is_auto_graded', 'is_correct', 'score', 'feedback', 'created_at'
        ]


class AnswerResponseSubmitSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(required=True)
    answer_text = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    answer_choice = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)
    assignment = AssignmentListSerializer(read_only=True)
    files = SubmissionFileSerializer(many=True, read_only=True)
    answers = AnswerResponseSerializer(many=True, read_only=True)
    grading_comments = serializers.SerializerMethodField()
    versions = serializers.SerializerMethodField()

    class Meta:
        model = AssignmentSubmission
        fields = [
            'id', 'assignment', 'student', 'text_answer', 'submission_status',
            'is_late', 'resubmission_count', 'total_score', 'penalty_score',
            'final_score', 'grading_status', 'graded_by', 'graded_at',
            'feedback', 'is_returned', 'files', 'answers', 'grading_comments',
            'versions', 'submitted_at', 'created_at', 'updated_at'
        ]

    def get_grading_comments(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user:
            comments = obj.grading_comments.all()
            if user == obj.student:
                comments = comments.filter(is_private=False)
            return GradingCommentSerializer(comments, many=True).data
        return []

    def get_versions(self, obj):
        return SubmissionVersionSerializer(obj.versions.all(), many=True).data


class GradingCommentSerializer(serializers.ModelSerializer):
    grader = UserMiniSerializer(read_only=True)

    class Meta:
        model = GradingComment
        fields = [
            'id', 'submission', 'grader', 'comment', 'comment_type',
            'is_private', 'created_at'
        ]


class SubmissionVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionVersion
        fields = [
            'id', 'submission', 'version_number', 'text_answer',
            'files', 'answers', 'submitted_at'
        ]


class AssignmentSubmissionCreateSerializer(serializers.Serializer):
    text_answer = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    answers = AnswerResponseSubmitSerializer(many=True, required=False, allow_empty=True)
    files = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True
    )


class GradingSerializer(serializers.Serializer):
    total_score = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    penalty_score = serializers.DecimalField(max_digits=5, decimal_places=2, default=0, required=False)
    feedback = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    comments = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True
    )
    question_scores = serializers.DictField(
        child=serializers.DecimalField(max_digits=5, decimal_places=2),
        required=False,
        allow_empty=True
    )
    is_returned = serializers.BooleanField(default=False, required=False)
