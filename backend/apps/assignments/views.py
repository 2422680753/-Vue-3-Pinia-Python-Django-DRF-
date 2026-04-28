from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Avg, Count, Sum
from django.core.files.base import ContentFile

from .models import (
    Assignment, AssignmentQuestion, GradingRubric,
    AssignmentSubmission, SubmissionFile, AnswerResponse,
    GradingComment, SubmissionVersion
)
from .serializers import (
    AssignmentListSerializer, AssignmentDetailSerializer,
    AssignmentCreateSerializer, AssignmentQuestionSerializer,
    GradingRubricSerializer, AssignmentSubmissionSerializer,
    SubmissionFileSerializer, AnswerResponseSerializer,
    AssignmentSubmissionCreateSerializer, GradingSerializer,
    GradingCommentSerializer, SubmissionVersionSerializer
)
from apps.courses.models import CourseEnrollment
from edu_platform.permissions import (
    IsTeacher, IsStudent, IsCourseInstructor, IsAssignmentOwner,
    IsAdminUser
)


class AssignmentViewSet(viewsets.ModelViewSet):
    queryset = Assignment.objects.select_related(
        'course', 'teacher', 'lesson'
    ).prefetch_related(
        'questions', 'rubrics', 'submissions'
    )
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['course', 'lesson', 'assignment_type', 'status']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'deadline', 'start_time']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return AssignmentListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return AssignmentCreateSerializer
        return AssignmentDetailSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsTeacher | IsAdminUser]
        return [p() for p in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_superuser or user.role == 'admin':
            return queryset
        elif user.role == 'teacher':
            return queryset.filter(teacher=user)
        else:
            enrolled_courses = CourseEnrollment.objects.filter(
                student=user, is_active=True
            ).values_list('course_id', flat=True)
            return queryset.filter(
                course_id__in=enrolled_courses,
                status='published'
            )

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_submission(self, request, pk=None):
        assignment = self.get_object()
        
        submission = AssignmentSubmission.objects.filter(
            assignment=assignment,
            student=request.user
        ).first()
        
        if submission:
            serializer = AssignmentSubmissionSerializer(
                submission,
                context={'request': request}
            )
            return Response(serializer.data)
        
        return Response(
            {'message': '您还没有提交作业'},
            status=status.HTTP_404_NOT_FOUND
        )

    @action(detail=True, methods=['get'], permission_classes=[IsCourseInstructor | IsAdminUser])
    def submissions(self, request, pk=None):
        assignment = self.get_object()
        submissions = assignment.submissions.select_related(
            'student'
        ).prefetch_related(
            'files', 'answers'
        )
        
        status_filter = request.query_params.get('status')
        if status_filter:
            submissions = submissions.filter(submission_status=status_filter)
        
        page = self.paginate_queryset(submissions)
        if page is not None:
            serializer = AssignmentSubmissionSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = AssignmentSubmissionSerializer(submissions, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[IsCourseInstructor | IsAdminUser])
    def stats(self, request, pk=None):
        assignment = self.get_object()
        submissions = assignment.submissions.all()
        
        total_students = CourseEnrollment.objects.filter(
            course=assignment.course,
            is_active=True
        ).count()
        
        submitted_count = submissions.filter(submission_status__in=['submitted', 'late', 'graded', 'returned']).count()
        late_count = submissions.filter(submission_status='late').count()
        graded_count = submissions.filter(submission_status='graded').count()
        
        scores = submissions.exclude(final_score__isnull=True).values_list('final_score', flat=True)
        avg_score = sum(scores) / len(scores) if scores else None
        
        score_distribution = {
            'excellent': 0,
            'good': 0,
            'pass': 0,
            'fail': 0
        }
        
        for score in scores:
            if score >= 90:
                score_distribution['excellent'] += 1
            elif score >= 80:
                score_distribution['good'] += 1
            elif score >= assignment.pass_score:
                score_distribution['pass'] += 1
            else:
                score_distribution['fail'] += 1
        
        return Response({
            'total_students': total_students,
            'submitted_count': submitted_count,
            'late_count': late_count,
            'graded_count': graded_count,
            'not_submitted_count': total_students - submitted_count,
            'average_score': avg_score,
            'score_distribution': score_distribution,
            'pass_score': assignment.pass_score
        })


class AssignmentSubmissionViewSet(viewsets.ModelViewSet):
    queryset = AssignmentSubmission.objects.select_related(
        'assignment', 'student', 'graded_by'
    ).prefetch_related(
        'files', 'answers', 'grading_comments', 'versions'
    )
    serializer_class = AssignmentSubmissionSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['assignment', 'submission_status', 'grading_status', 'is_late']
    ordering_fields = ['submitted_at', 'final_score', 'created_at']
    ordering = ['-submitted_at']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['create', 'update', 'partial_update']:
            permission_classes = [IsStudent]
        elif self.action in ['destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [p() for p in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_superuser or user.role == 'admin':
            return queryset
        elif user.role == 'teacher':
            return queryset.filter(assignment__teacher=user)
        else:
            return queryset.filter(student=user)

    def _save_version(self, submission):
        version_number = submission.versions.count() + 1
        
        answer_data = []
        for answer in submission.answers.all():
            answer_data.append({
                'question_id': answer.question.id,
                'answer_text': answer.answer_text,
                'answer_choice': answer.answer_choice
            })
        
        file_data = []
        for file_obj in submission.files.all():
            file_data.append({
                'id': file_obj.id,
                'filename': file_obj.filename,
                'file_size': file_obj.file_size
            })
        
        SubmissionVersion.objects.create(
            submission=submission,
            version_number=version_number,
            text_answer=submission.text_answer,
            files=file_data,
            answers=answer_data,
            submitted_at=submission.submitted_at if submission.submitted_at else timezone.now()
        )

    @action(detail=False, methods=['post'])
    def submit(self, request):
        assignment_id = request.data.get('assignment_id')
        if not assignment_id:
            return Response(
                {'error': '请提供作业ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            assignment = Assignment.objects.get(id=assignment_id)
        except Assignment.DoesNotExist:
            return Response(
                {'error': '作业不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        now = timezone.now()
        
        if now < assignment.start_time:
            return Response(
                {'error': '作业还未开始提交'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if assignment.deadline and now > assignment.deadline:
            if not assignment.allow_late_submission:
                return Response(
                    {'error': '作业已截止，不允许提交'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if assignment.late_deadline and now > assignment.late_deadline:
                return Response(
                    {'error': '迟交截止时间已过'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        submission, created = AssignmentSubmission.objects.get_or_create(
            assignment=assignment,
            student=request.user,
            defaults={
                'submission_status': 'not_submitted',
                'grading_status': 'pending'
            }
        )
        
        if not created and submission.submission_status in ['submitted', 'late', 'graded']:
            if not assignment.allow_resubmission:
                return Response(
                    {'error': '该作业不允许重做提交'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if submission.resubmission_count >= assignment.max_resubmissions:
                return Response(
                    {'error': f'最多只能重做{assignment.max_resubmissions}次'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        self._save_version(submission)
        
        serializer = AssignmentSubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        text_answer = serializer.validated_data.get('text_answer')
        answers_data = serializer.validated_data.get('answers', [])
        
        submission.text_answer = text_answer
        
        is_late = assignment.deadline and now > assignment.deadline
        submission.is_late = is_late
        submission.submission_status = 'late' if is_late else 'submitted'
        submission.grading_status = 'pending'
        submission.submitted_at = now
        
        if not created and submission.submission_status in ['submitted', 'late']:
            submission.resubmission_count += 1
        
        submission.save()
        
        if answers_data:
            AnswerResponse.objects.filter(submission=submission).delete()
            for ans_data in answers_data:
                try:
                    question = AssignmentQuestion.objects.get(
                        id=ans_data.get('question_id'),
                        assignment=assignment
                    )
                    AnswerResponse.objects.create(
                        submission=submission,
                        question=question,
                        answer_text=ans_data.get('answer_text'),
                        answer_choice=ans_data.get('answer_choice', [])
                    )
                except AssignmentQuestion.DoesNotExist:
                    continue
        
        files = request.FILES.getlist('files')
        if files and assignment.allows_file_upload:
            SubmissionFile.objects.filter(submission=submission).delete()
            for file_obj in files[:assignment.max_file_count]:
                file_type = file_obj.name.split('.')[-1].lower() if '.' in file_obj.name else ''
                
                if assignment.allowed_file_types and file_type not in assignment.allowed_file_types:
                    continue
                
                file_size = file_obj.size
                if file_size > assignment.max_file_size * 1024 * 1024:
                    continue
                
                SubmissionFile.objects.create(
                    submission=submission,
                    file=file_obj,
                    filename=file_obj.name,
                    file_size=file_size,
                    file_type=file_type
                )
        
        return Response(
            AssignmentSubmissionSerializer(submission, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsTeacher | IsAdminUser])
    def grade(self, request, pk=None):
        submission = self.get_object()
        assignment = submission.assignment
        
        serializer = GradingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        total_score = serializer.validated_data.get('total_score')
        penalty_score = serializer.validated_data.get('penalty_score', 0)
        feedback = serializer.validated_data.get('feedback')
        comments = serializer.validated_data.get('comments', [])
        question_scores = serializer.validated_data.get('question_scores', {})
        is_returned = serializer.validated_data.get('is_returned', False)
        
        for question_id, score in question_scores.items():
            try:
                answer = AnswerResponse.objects.get(
                    submission=submission,
                    question_id=question_id
                )
                answer.score = score
                answer.feedback = feedback
                answer.save()
            except AnswerResponse.DoesNotExist:
                continue
        
        if total_score is None:
            answer_scores = submission.answers.exclude(score__isnull=True).values_list('score', flat=True)
            total_score = sum(answer_scores) if answer_scores else 0
        
        if submission.is_late and assignment.late_submission_penalty > 0:
            days_late = (submission.submitted_at - assignment.deadline).days if assignment.deadline else 0
            if days_late > 0:
                penalty = min(
                    assignment.total_score * assignment.late_submission_penalty * days_late,
                    total_score
                )
                penalty_score = max(penalty_score, penalty)
        
        submission.total_score = total_score
        submission.penalty_score = penalty_score
        submission.final_score = max(0, total_score - penalty_score)
        
        submission.graded_by = request.user
        submission.graded_at = timezone.now()
        
        if is_returned:
            submission.is_returned = True
            submission.submission_status = 'returned'
            submission.grading_status = 'completed'
        else:
            submission.submission_status = 'graded'
            submission.grading_status = 'completed'
        
        submission.feedback = feedback
        submission.save()
        
        for comment_data in comments:
            GradingComment.objects.create(
                submission=submission,
                grader=request.user,
                comment=comment_data.get('comment', ''),
                comment_type=comment_data.get('comment_type', 'general'),
                is_private=comment_data.get('is_private', False)
            )
        
        return Response(
            AssignmentSubmissionSerializer(submission, context={'request': request}).data
        )

    @action(detail=True, methods=['post'], permission_classes=[IsTeacher | IsAdminUser])
    def add_comment(self, request, pk=None):
        submission = self.get_object()
        
        comment = request.data.get('comment')
        comment_type = request.data.get('comment_type', 'general')
        is_private = request.data.get('is_private', False)
        
        if not comment:
            return Response(
                {'error': '请提供评语内容'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        grading_comment = GradingComment.objects.create(
            submission=submission,
            grader=request.user,
            comment=comment,
            comment_type=comment_type,
            is_private=is_private
        )
        
        return Response(
            GradingCommentSerializer(grading_comment).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        submission = self.get_object()
        versions = submission.versions.all()
        serializer = SubmissionVersionSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def compare_versions(self, request, pk=None):
        submission = self.get_object()
        version1 = request.query_params.get('v1')
        version2 = request.query_params.get('v2')
        
        try:
            v1 = submission.versions.get(version_number=version1)
            v2 = submission.versions.get(version_number=version2)
        except SubmissionVersion.DoesNotExist as e:
            return Response(
                {'error': f'版本不存在: {e}'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            'version1': SubmissionVersionSerializer(v1).data,
            'version2': SubmissionVersionSerializer(v2).data,
            'diff': {
                'text_answer_changed': v1.text_answer != v2.text_answer,
                'files_changed': len(v1.files) != len(v2.files),
                'answers_changed': len(v1.answers) != len(v2.answers)
            }
        })
