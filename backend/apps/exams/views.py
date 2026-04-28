from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Avg, Count, Sum, Q
from django.db import transaction
import random

from .models import (
    Exam, QuestionBank, ExamQuestion, ExamAttempt,
    ExamAnswer, CheatingRecord, ExamActivityLog
)
from .serializers import (
    ExamListSerializer, ExamDetailSerializer, ExamCreateSerializer,
    QuestionBankSerializer, QuestionBankListSerializer,
    ExamQuestionSerializer, ExamAttemptSerializer,
    ExamAnswerSerializer, ExamAnswerSubmitSerializer,
    CheatingRecordSerializer, ExamActivityLogSerializer,
    ExamStartSerializer, AntiCheatingEventSerializer
)
from apps.courses.models import CourseEnrollment
from edu_platform.permissions import (
    IsTeacher, IsStudent, IsAdminUser, IsExamAttemptOwner
)


class QuestionBankViewSet(viewsets.ModelViewSet):
    queryset = QuestionBank.objects.select_related(
        'course', 'chapter', 'teacher'
    )
    serializer_class = QuestionBankSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['course', 'chapter', 'question_type', 'difficulty', 'is_active']
    search_fields = ['question_text', 'explanation']
    ordering_fields = ['created_at', 'usage_count', 'correct_rate']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsTeacher | IsAdminUser]
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
        return queryset.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return QuestionBankListSerializer
        return QuestionBankSerializer

    def perform_create(self, serializer):
        serializer.save(teacher=self.request.user)


class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.select_related(
        'course', 'teacher'
    ).prefetch_related(
        'exam_questions', 'attempts'
    )
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['course', 'exam_type', 'status']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'start_time', 'end_time']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return ExamListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ExamCreateSerializer
        return ExamDetailSerializer

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

    @action(detail=False, methods=['get'])
    def my_exams(self, request):
        user = request.user
        now = timezone.now()
        
        enrolled_courses = CourseEnrollment.objects.filter(
            student=user, is_active=True
        ).values_list('course_id', flat=True)
        
        exams = Exam.objects.filter(
            course_id__in=enrolled_courses,
            status='published'
        )
        
        upcoming = exams.filter(start_time__gt=now)
        ongoing = exams.filter(start_time__lte=now, end_time__gte=now)
        completed = exams.filter(end_time__lt=now)
        
        return Response({
            'upcoming': ExamListSerializer(upcoming, many=True, context={'request': request}).data,
            'ongoing': ExamListSerializer(ongoing, many=True, context={'request': request}).data,
            'completed': ExamListSerializer(completed, many=True, context={'request': request}).data,
        })

    @action(detail=True, methods=['post'], permission_classes=[IsStudent])
    def start(self, request, pk=None):
        exam = self.get_object()
        serializer = ExamStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        now = timezone.now()
        
        if exam.password:
            provided_password = serializer.validated_data.get('password')
            if provided_password != exam.password:
                return Response(
                    {'error': '考试密码错误'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if exam.status != 'published':
            return Response(
                {'error': '考试未发布'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        enter_allowed_time = exam.start_time - timezone.timedelta(minutes=exam.allow_enter_before)
        if now < enter_allowed_time:
            return Response(
                {'error': f'考试还未开始，最早可提前{exam.allow_enter_before}分钟进入'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if now > exam.end_time:
            return Response(
                {'error': '考试已结束'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if now > exam.start_time and not exam.allow_late_enter:
            return Response(
                {'error': '考试已开始，不允许迟到进入'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if now > exam.start_time and exam.allow_late_enter:
            late_minutes = (now - exam.start_time).total_seconds() / 60
            if exam.late_enter_limit and late_minutes > exam.late_enter_limit:
                return Response(
                    {'error': f'迟到超过{exam.late_enter_limit}分钟，不允许进入'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        existing_attempts = ExamAttempt.objects.filter(exam=exam, student=request.user)
        if existing_attempts.count() >= exam.max_attempts:
            return Response(
                {'error': f'您已参加{exam.max_attempts}次考试，无法再次参加'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        in_progress_attempt = existing_attempts.filter(status='in_progress').first()
        if in_progress_attempt:
            return Response(
                ExamAttemptSerializer(in_progress_attempt).data
            )
        
        with transaction.atomic():
            attempt_number = existing_attempts.count() + 1
            
            attempt = ExamAttempt.objects.create(
                exam=exam,
                student=request.user,
                attempt_number=attempt_number,
                status='in_progress',
                ip_address=request.META.get('REMOTE_ADDR', 'unknown'),
                device_info=request.META.get('HTTP_USER_AGENT', 'unknown')
            )
            
            questions = list(exam.exam_questions.all())
            
            if exam.is_shuffle_questions:
                random.shuffle(questions)
            
            attempt.shuffled_questions = [q.id for q in questions]
            
            if exam.is_shuffle_options:
                shuffled_options = {}
                for q in questions:
                    if q.options:
                        options = list(q.options)
                        random.shuffle(options)
                        shuffled_options[q.id] = [opt['value'] for opt in options]
                attempt.shuffled_options = shuffled_options
            
            attempt.save()
            
            for question in questions:
                ExamAnswer.objects.create(
                    attempt=attempt,
                    question=question,
                    is_answered=False,
                    is_skipped=False
                )
        
        return Response(
            ExamAttemptSerializer(attempt).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['get'], permission_classes=[IsTeacher | IsAdminUser])
    def attempts(self, request, pk=None):
        exam = self.get_object()
        attempts = exam.attempts.select_related(
            'student'
        ).prefetch_related(
            'answers', 'cheating_records'
        )
        
        status_filter = request.query_params.get('status')
        if status_filter:
            attempts = attempts.filter(status=status_filter)
        
        page = self.paginate_queryset(attempts)
        if page is not None:
            serializer = ExamAttemptSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ExamAttemptSerializer(attempts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[IsTeacher | IsAdminUser])
    def stats(self, request, pk=None):
        exam = self.get_object()
        attempts = exam.attempts.all()
        
        total_students = CourseEnrollment.objects.filter(
            course=exam.course,
            is_active=True
        ).count()
        
        started_count = attempts.count()
        completed_count = attempts.filter(status__in=['submitted', 'graded']).count()
        graded_count = attempts.filter(status='graded').count()
        
        cheating_count = attempts.filter(is_cheating_detected=True).count()
        
        scores = attempts.exclude(total_score__isnull=True).values_list('total_score', flat=True)
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
            elif score >= exam.pass_score:
                score_distribution['pass'] += 1
            else:
                score_distribution['fail'] += 1
        
        pass_count = sum(1 for s in scores if s >= exam.pass_score)
        pass_rate = pass_count / len(scores) if scores else 0
        
        cheating_stats = CheatingRecord.objects.filter(attempt__exam=exam).values(
            'cheating_type'
        ).annotate(count=Count('id'))
        
        return Response({
            'total_students': total_students,
            'started_count': started_count,
            'completed_count': completed_count,
            'graded_count': graded_count,
            'not_started_count': total_students - started_count,
            'average_score': avg_score,
            'pass_score': exam.pass_score,
            'pass_rate': pass_rate,
            'score_distribution': score_distribution,
            'cheating_count': cheating_count,
            'cheating_by_type': [
                {'type': stat['cheating_type'], 'count': stat['count']
                for stat in cheating_stats
            ]
        })

    @action(detail=True, methods=['post'], permission_classes=[IsTeacher | IsAdminUser])
    def add_questions(self, request, pk=None):
        exam = self.get_object()
        question_ids = request.data.get('question_ids', [])
        
        if not question_ids:
            return Response(
                {'error': '请提供题目ID列表'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        questions = QuestionBank.objects.filter(
            id__in=question_ids, teacher=request.user
        )
        
        if questions.count() != len(question_ids):
            return Response(
                {'error': '部分题目不存在或无权限'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        exam_questions = []
        current_order = exam.exam_questions.count()
        
        for question in questions:
            current_order += 1
            exam_questions.append(ExamQuestion(
                exam=exam,
                question_bank=question,
                question_text=question.question_text,
                question_type=question.question_type,
                options=question.options,
                correct_answer=question.correct_answer,
                question_order=current_order,
                score=question.score,
                explanation=question.explanation
            ))
        
        ExamQuestion.objects.bulk_create(exam_questions)
        
        exam.total_questions = exam.exam_questions.count()
        exam.total_score = sum(q.score for q in exam.exam_questions.all())
        exam.save()
        
        return Response({'message': f'成功添加{len(exam_questions)}道题目'})

    @action(detail=True, methods=['post'], permission_classes=[IsTeacher | IsAdminUser])
    def generate_from_bank(self, request, pk=None):
        exam = self.get_object()
        
        question_count = request.data.get('question_count', 10)
        difficulty_distribution = request.data.get('difficulty_distribution', {
            'easy': 0.3,
            'medium': 0.5,
            'hard': 0.2
        })
        
        questions = QuestionBank.objects.filter(
            course=exam.course,
            is_active=True
        )
        
        if not questions.exists():
            return Response(
                {'error': '题库中没有可用题目'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        selected_questions = []
        
        for difficulty, ratio in difficulty_distribution.items():
            count = int(question_count * ratio)
            diff_questions = list(questions.filter(difficulty=difficulty))
            
            if len(diff_questions) < count:
                count = len(diff_questions)
            
            selected = random.sample(diff_questions, count)
            selected_questions.extend(selected)
        
        if not selected_questions:
            return Response(
                {'error': '无法从题库中选择题目'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        exam_questions = []
        for i, question in enumerate(selected_questions, 1):
            exam_questions.append(ExamQuestion(
                exam=exam,
                question_bank=question,
                question_text=question.question_text,
                question_type=question.question_type,
                options=question.options,
                correct_answer=question.correct_answer,
                question_order=i,
                score=question.score,
                explanation=question.explanation
            ))
        
        ExamQuestion.objects.bulk_create(exam_questions)
        
        exam.total_questions = len(exam_questions)
        exam.total_score = sum(q.score for q in exam.exam_questions.all())
        exam.save()
        
        return Response({
            'message': f'成功从题库生成{len(exam_questions)}道题目'
        })


class ExamAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ExamAttempt.objects.select_related(
        'exam', 'student', 'graded_by'
    ).prefetch_related(
        'answers', 'answers__question', 'cheating_records', 'activity_logs'
    )
    serializer_class = ExamAttemptSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['exam', 'status', 'is_cheating_detected']
    ordering_fields = ['created_at', 'start_time', 'total_score']
    ordering = ['-created_at']

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_superuser or user.role == 'admin':
            return queryset
        elif user.role == 'teacher':
            return queryset.filter(exam__teacher=user)
        else:
            return queryset.filter(student=user)

    @action(detail=False, methods=['get'])
    def my_attempts(self, request):
        attempts = self.get_queryset().filter(student=request.user)
        return Response(ExamAttemptSerializer(attempts, many=True).data)

    @action(detail=True, methods=['post'], permission_classes=[IsStudent])
    def submit(self, request, pk=None):
        attempt = self.get_object()
        
        if attempt.status != 'in_progress':
            return Response(
                {'error': '考试不在进行中'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        now = timezone.now()
        
        attempt.status = 'submitted'
        attempt.submitted_manually = True
        attempt.submit_time = now
        attempt.end_time = now
        
        if attempt.start_time:
            attempt.time_spent = int((attempt.end_time - attempt.start_time).total_seconds())
        
        attempt.save()
        
        if attempt.exam.exam_questions.filter(question_type__in=[
            'single_choice', 'multi_choice', 'true_false', 'fill_blank'
        ]):
            self._auto_grade(attempt)
        
        return Response(ExamAttemptSerializer(attempt).data)

    def _auto_grade(self, attempt):
        answers = attempt.answers.select_related('question').all()
        
        total_score = 0
        correct_count = 0
        incorrect_count = 0
        
        for answer in answers:
            question = answer.question
            is_correct = None
            
            if question.question_type == 'single_choice':
                if answer.answer_choice and len(answer.answer_choice) == 1:
                    correct_ans = question.correct_answer.get('answer')
                    is_correct = answer.answer_choice[0] == correct_ans
            
            elif question.question_type == 'multi_choice':
                if answer.answer_choice:
                    correct_ans = set(question.correct_answer.get('answers', []))
                    student_ans = set(answer.answer_choice)
                    is_correct = student_ans == correct_ans
            
            elif question.question_type == 'true_false':
                if answer.answer_choice and len(answer.answer_choice) == 1:
                    correct_ans = question.correct_answer.get('answer')
                    is_correct = answer.answer_choice[0] == correct_ans
            
            elif question.question_type == 'fill_blank':
                if answer.answer_text:
                    correct_ans = question.correct_answer.get('answers', [])
                    is_correct = any(
                        ans.strip().lower() == answer.answer_text.strip().lower()
                        for ans in correct_ans
                    )
            
            if is_correct is not None:
                answer.is_correct = is_correct
                answer.score = question.score if is_correct else 0
                answer.is_auto_graded = True
                answer.save()
                
                if is_correct:
                    total_score += question.score
                    correct_count += 1
                else:
                    incorrect_count += 1
        
        attempt.total_score = total_score
        attempt.correct_count = correct_count
        attempt.incorrect_count = incorrect_count
        attempt.unanswered_count = attempt.answers.filter(is_answered=False).count()
        
        if attempt.total_score is not None and attempt.exam.total_score > 0:
            attempt.score_percentage = attempt.total_score / attempt.exam.total_score
            attempt.is_passed = attempt.total_score >= attempt.exam.pass_score
        
        if attempt.exam.show_score_immediately:
            attempt.status = 'graded'
        
        attempt.save()

    @action(detail=True, methods=['get'], permission_classes=[IsTeacher | IsAdminUser])
    def grade(self, request, pk=None):
        attempt = self.get_object()
        
        if attempt.status != 'submitted':
            return Response(
                {'error': '考试未提交'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        question_scores = request.data.get('question_scores', {})
        total_score = request.data.get('total_score')
        feedback = request.data.get('feedback')
        
        for question_id, score in question_scores.items():
            try:
                answer = ExamAnswer.objects.get(
                    attempt=attempt,
                    question_id=question_id
                )
                answer.score = score
                answer.teacher_feedback = request.data.get(f'feedback_{question_id}')
                answer.is_correct = score == answer.question.score
                answer.save()
            except ExamAnswer.DoesNotExist:
                continue
        
        if total_score is None:
            answer_scores = attempt.answers.values_list('score', flat=True)
            total_score = sum(s for s in answer_scores if s is not None)
        
        attempt.total_score = total_score
        attempt.score_percentage = total_score / attempt.exam.total_score if attempt.exam.total_score > 0 else 0
        attempt.is_passed = total_score >= attempt.exam.pass_score
        attempt.feedback = feedback
        attempt.graded_by = request.user
        attempt.graded_at = timezone.now()
        attempt.status = 'graded'
        
        attempt.correct_count = attempt.answers.filter(is_correct=True).count()
        attempt.incorrect_count = attempt.answers.filter(is_correct=False).count()
        attempt.unanswered_count = attempt.answers.filter(is_answered=False).count()
        
        attempt.save()
        
        return Response(ExamAttemptSerializer(attempt).data)

    @action(detail=True, methods=['get'])
    def answers(self, request, pk=None):
        attempt = self.get_object()
        answers = attempt.answers.select_related('question')
        
        show_correct = False
        if request.user.role in ['teacher', 'admin'] or request.user.is_superuser:
            show_correct = True
        elif attempt.exam.show_answers_after_exam and attempt.status in ['submitted', 'graded']:
            show_correct = True
        
        serializer = ExamAnswerSerializer(answers, many=True)
        data = serializer.data
        
        if not show_correct:
            for item in data:
                item.pop('is_correct', None)
                item.pop('score', None)
                item.pop('teacher_feedback', None)
        
        return Response(data)

    @action(detail=True, methods=['get'])
    def cheating_records(self, request, pk=None):
        attempt = self.get_object()
        records = attempt.cheating_records.all()
        return Response(CheatingRecordSerializer(records, many=True).data)

    @action(detail=True, methods=['get'])
    def activity_logs(self, request, pk=None):
        attempt = self.get_object()
        logs = attempt.activity_logs.all()
        return Response(ExamActivityLogSerializer(logs, many=True).data)

    @action(detail=True, methods=['post'], permission_classes=[IsTeacher | IsAdminUser])
    def mark_cheating(self, request, pk=None):
        attempt = self.get_object()
        
        cheating_type = request.data.get('cheating_type')
        description = request.data.get('description', '')
        severity = request.data.get('severity', 'medium')
        action_taken = request.data.get('action_taken')
        
        if not cheating_type:
            return Response(
                {'error': '请提供作弊类型'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        record = CheatingRecord.objects.create(
            attempt=attempt,
            cheating_type=cheating_type,
            description=description,
            severity=severity,
            action_taken=action_taken,
            is_verified=True,
            verified_by=request.user,
            verified_at=timezone.now()
        )
        
        if severity == 'high' or action_taken in ['forced_submit', 'score_zero', 'ban']:
            attempt.is_cheating_detected = True
            attempt.cheating_reason = description
            attempt.save()
        
        return Response(CheatingRecordSerializer(record).data)
