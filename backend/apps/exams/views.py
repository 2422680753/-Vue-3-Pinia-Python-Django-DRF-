from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Avg, Count, Sum, Q
from django.db import transaction
import random
import hashlib
import logging

logger = logging.getLogger(__name__)

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
    ExamStartSerializer, AntiCheatingEventSerializer,
    ExamBatchGradeSerializer, ExamAnswerBatchSubmitSerializer
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
        
        request_id = serializer.validated_data.get('request_id')
        
        try:
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
            
            with transaction.atomic():
                existing_attempts = ExamAttempt.objects.select_for_update().filter(
                    exam=exam,
                    student=request.user
                )
                
                in_progress_attempt = existing_attempts.filter(status='in_progress').first()
                if in_progress_attempt:
                    logger.info(
                        f'User {request.user.id} returning to exam {exam.id}, '
                        f'attempt {in_progress_attempt.id}'
                    )
                    return Response(ExamAttemptSerializer(in_progress_attempt).data)
                
                if existing_attempts.count() >= exam.max_attempts:
                    return Response(
                        {'error': f'您已参加{exam.max_attempts}次考试，无法再次参加'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                attempt_number = existing_attempts.count() + 1
                
                attempt = ExamAttempt.objects.create(
                    exam=exam,
                    student=request.user,
                    attempt_number=attempt_number,
                    status='in_progress',
                    start_time=now,
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
                
                ExamActivityLog.objects.create(
                    attempt=attempt,
                    activity_type='start',
                    details={
                        'ip': request.META.get('REMOTE_ADDR', 'unknown'),
                        'user_agent': request.META.get('HTTP_USER_AGENT', 'unknown'),
                        'attempt_number': attempt_number,
                        'request_id': request_id
                    }
                )
            
            logger.info(
                f'User {request.user.id} started exam {exam.id}, '
                f'attempt {attempt_number}'
            )
            
            return Response(
                ExamAttemptSerializer(attempt).data,
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            logger.error(
                f'Error starting exam {exam.id} for user {request.user.id}: {str(e)}',
                exc_info=True
            )
            return Response(
                {'error': '开始考试时发生错误，请稍后重试'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
    def submit_answer(self, request, pk=None):
        """提交单题答案"""
        attempt = self.get_object()
        
        serializer = ExamAnswerSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            if attempt.status != 'in_progress':
                return Response(
                    {'error': '考试不在进行中'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            question_id = serializer.validated_data['question_id']
            
            with transaction.atomic():
                try:
                    answer = ExamAnswer.objects.select_for_update().get(
                        attempt=attempt,
                        question_id=question_id
                    )
                except ExamAnswer.DoesNotExist:
                    return Response(
                        {'error': '题目不存在'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                answer.answer_text = serializer.validated_data.get('answer_text')
                answer.answer_choice = serializer.validated_data.get('answer_choice', [])
                answer.is_skipped = serializer.validated_data.get('is_skipped', False)
                answer.is_flagged = serializer.validated_data.get('is_flagged', False)
                
                time_spent = serializer.validated_data.get('time_spent')
                if time_spent is not None:
                    answer.time_spent = time_spent
                
                if answer.answer_text or answer.answer_choice:
                    answer.is_answered = True
                else:
                    answer.is_answered = False
                
                answer.save()
                
                ExamActivityLog.objects.create(
                    attempt=attempt,
                    activity_type='answer',
                    details={
                        'question_id': question_id,
                        'is_answered': answer.is_answered,
                        'is_skipped': answer.is_skipped,
                        'is_flagged': answer.is_flagged,
                        'time_spent': time_spent
                    }
                )
            
            logger.info(
                f'User {request.user.id} submitted answer for question {question_id} '
                f'in exam attempt {attempt.id}'
            )
            
            return Response({
                'status': 'success',
                'question_id': question_id,
                'is_answered': answer.is_answered
            })
        
        except Exception as e:
            logger.error(
                f'Error submitting answer for attempt {attempt.id}: {str(e)}',
                exc_info=True
            )
            return Response(
                {'error': '提交答案时发生错误'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsStudent])
    def submit_answers_batch(self, request, pk=None):
        """批量提交答案"""
        attempt = self.get_object()
        
        serializer = ExamAnswerBatchSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            if attempt.status != 'in_progress':
                return Response(
                    {'error': '考试不在进行中'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            answers_data = serializer.validated_data['answers']
            request_id = serializer.validated_data.get('request_id')
            
            if not answers_data:
                return Response(
                    {'error': '没有答案数据'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            question_ids = [a['question_id'] for a in answers_data]
            if len(question_ids) != len(set(question_ids)):
                return Response(
                    {'error': '存在重复的题目ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            updated_count = 0
            
            with transaction.atomic():
                for ans_data in answers_data:
                    question_id = ans_data['question_id']
                    
                    try:
                        answer = ExamAnswer.objects.select_for_update().get(
                            attempt=attempt,
                            question_id=question_id
                        )
                    except ExamAnswer.DoesNotExist:
                        continue
                    
                    answer.answer_text = ans_data.get('answer_text')
                    answer.answer_choice = ans_data.get('answer_choice', [])
                    answer.is_skipped = ans_data.get('is_skipped', False)
                    answer.is_flagged = ans_data.get('is_flagged', False)
                    
                    time_spent = ans_data.get('time_spent')
                    if time_spent is not None:
                        answer.time_spent = time_spent
                    
                    if answer.answer_text or answer.answer_choice:
                        answer.is_answered = True
                    else:
                        answer.is_answered = False
                    
                    answer.save()
                    updated_count += 1
                
                ExamActivityLog.objects.create(
                    attempt=attempt,
                    activity_type='answer',
                    details={
                        'batch_size': len(answers_data),
                        'updated_count': updated_count,
                        'request_id': request_id
                    }
                )
            
            logger.info(
                f'User {request.user.id} batch submitted {updated_count} answers '
                f'for attempt {attempt.id}'
            )
            
            return Response({
                'status': 'success',
                'updated_count': updated_count
            })
        
        except Exception as e:
            logger.error(
                f'Error batch submitting answers for attempt {attempt.id}: {str(e)}',
                exc_info=True
            )
            return Response(
                {'error': '批量提交答案时发生错误'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsStudent])
    def submit(self, request, pk=None):
        """提交考试"""
        attempt = self.get_object()
        
        try:
            if attempt.status != 'in_progress':
                if attempt.status in ['submitted', 'graded']:
                    return Response(ExamAttemptSerializer(attempt).data)
                return Response(
                    {'error': '考试不在进行中'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            now = timezone.now()
            
            with transaction.atomic():
                attempt = ExamAttempt.objects.select_for_update().get(id=attempt.id)
                
                if attempt.status != 'in_progress':
                    return Response(ExamAttemptSerializer(attempt).data)
                
                attempt.status = 'submitted'
                attempt.submitted_manually = True
                attempt.submit_time = now
                attempt.end_time = now
                
                if attempt.start_time:
                    attempt.time_spent = int((attempt.end_time - attempt.start_time).total_seconds())
                
                attempt.save()
                
                ExamActivityLog.objects.create(
                    attempt=attempt,
                    activity_type='submit',
                    details={
                        'time_spent': attempt.time_spent,
                        'submitted_manually': True,
                        'timestamp': now.isoformat()
                    }
                )
                
                self._auto_grade(attempt)
            
            logger.info(
                f'User {request.user.id} submitted exam attempt {attempt.id}, '
                f'score: {attempt.total_score}'
            )
            
            return Response(ExamAttemptSerializer(attempt).data)
        
        except Exception as e:
            logger.error(
                f'Error submitting exam attempt {attempt.id}: {str(e)}',
                exc_info=True
            )
            return Response(
                {'error': '提交考试时发生错误'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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

    @action(detail=True, methods=['post'], permission_classes=[IsTeacher | IsAdminUser])
    def grade(self, request, pk=None):
        """批改考试"""
        attempt = self.get_object()
        
        try:
            if attempt.status != 'submitted':
                if attempt.status == 'graded':
                    return Response(ExamAttemptSerializer(attempt).data)
                return Response(
                    {'error': '考试未提交，无法批改'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            question_scores = request.data.get('question_scores', {})
            total_score = request.data.get('total_score')
            feedback = request.data.get('feedback')
            
            if total_score is not None:
                if total_score < 0 or total_score > attempt.exam.total_score:
                    return Response(
                        {'error': f'总分应在0到{attempt.exam.total_score}之间'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            with transaction.atomic():
                for question_id, score in question_scores.items():
                    if score < 0:
                        return Response(
                            {'error': f'题目分数不能为负数'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    try:
                        answer = ExamAnswer.objects.get(
                            attempt=attempt,
                            question_id=question_id
                        )
                        
                        max_score = answer.question.score
                        if score > max_score:
                            return Response(
                                {'error': f'题目{question_id}分数不能超过{max_score}'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        
                        answer.score = score
                        answer.teacher_feedback = request.data.get(f'feedback_{question_id}')
                        answer.is_correct = score == max_score
                        answer.graded_by = request.user
                        answer.graded_at = timezone.now()
                        answer.save()
                    except ExamAnswer.DoesNotExist:
                        continue
                
                if total_score is None:
                    answer_scores = attempt.answers.values_list('score', flat=True)
                    total_score = sum(s for s in answer_scores if s is not None)
                
                attempt.total_score = total_score
                attempt.score_percentage = (
                    total_score / attempt.exam.total_score 
                    if attempt.exam.total_score > 0 else 0
                )
                attempt.is_passed = total_score >= attempt.exam.pass_score
                attempt.feedback = feedback
                attempt.graded_by = request.user
                attempt.graded_at = timezone.now()
                attempt.status = 'graded'
                
                attempt.correct_count = attempt.answers.filter(is_correct=True).count()
                attempt.incorrect_count = attempt.answers.filter(
                    is_answered=True, is_correct=False
                ).count()
                attempt.unanswered_count = attempt.answers.filter(is_answered=False).count()
                
                attempt.save()
            
            logger.info(
                f'Teacher {request.user.id} graded exam attempt {attempt.id}, '
                f'score: {total_score}'
            )
            
            return Response(ExamAttemptSerializer(attempt).data)
        
        except Exception as e:
            logger.error(
                f'Error grading exam attempt {attempt.id}: {str(e)}',
                exc_info=True
            )
            return Response(
                {'error': '批改考试时发生错误'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], permission_classes=[IsTeacher | IsAdminUser])
    def batch_grade(self, request):
        """批量批改考试"""
        serializer = ExamBatchGradeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            grades_data = serializer.validated_data['grades']
            request_id = serializer.validated_data.get('request_id')
            
            if not grades_data:
                return Response(
                    {'error': '没有批改数据'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            attempt_ids = [g['attempt_id'] for g in grades_data]
            if len(attempt_ids) != len(set(attempt_ids)):
                return Response(
                    {'error': '存在重复的考试记录ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            results = []
            errors = []
            
            with transaction.atomic():
                for grade_data in grades_data:
                    attempt_id = grade_data['attempt_id']
                    total_score = grade_data['total_score']
                    feedback = grade_data.get('feedback')
                    question_scores = grade_data.get('question_scores', {})
                    
                    try:
                        attempt = ExamAttempt.objects.select_for_update().get(id=attempt_id)
                        
                        if attempt.status != 'submitted':
                            errors.append({
                                'attempt_id': attempt_id,
                                'error': '考试未提交'
                            })
                            continue
                        
                        if total_score < 0 or total_score > attempt.exam.total_score:
                            errors.append({
                                'attempt_id': attempt_id,
                                'error': f'总分应在0到{attempt.exam.total_score}之间'
                            })
                            continue
                        
                        for question_id, score in question_scores.items():
                            if score < 0:
                                errors.append({
                                    'attempt_id': attempt_id,
                                    'error': '题目分数不能为负数'
                                })
                                raise Exception('无效分数')
                            
                            try:
                                answer = ExamAnswer.objects.get(
                                    attempt=attempt,
                                    question_id=question_id
                                )
                                
                                max_score = answer.question.score
                                if score > max_score:
                                    errors.append({
                                        'attempt_id': attempt_id,
                                        'error': f'题目{question_id}分数不能超过{max_score}'
                                    })
                                    raise Exception('无效分数')
                                
                                answer.score = score
                                answer.is_correct = score == max_score
                                answer.graded_by = request.user
                                answer.graded_at = timezone.now()
                                answer.save()
                            except ExamAnswer.DoesNotExist:
                                continue
                        
                        attempt.total_score = total_score
                        attempt.score_percentage = (
                            total_score / attempt.exam.total_score 
                            if attempt.exam.total_score > 0 else 0
                        )
                        attempt.is_passed = total_score >= attempt.exam.pass_score
                        attempt.feedback = feedback
                        attempt.graded_by = request.user
                        attempt.graded_at = timezone.now()
                        attempt.status = 'graded'
                        
                        attempt.correct_count = attempt.answers.filter(is_correct=True).count()
                        attempt.incorrect_count = attempt.answers.filter(
                            is_answered=True, is_correct=False
                        ).count()
                        attempt.unanswered_count = attempt.answers.filter(
                            is_answered=False
                        ).count()
                        
                        attempt.save()
                        
                        results.append({
                            'attempt_id': attempt_id,
                            'status': 'success',
                            'total_score': float(total_score)
                        })
                        
                    except ExamAttempt.DoesNotExist:
                        errors.append({
                            'attempt_id': attempt_id,
                            'error': '考试记录不存在'
                        })
                    except Exception as e:
                        if not errors or errors[-1].get('attempt_id') != attempt_id:
                            errors.append({
                                'attempt_id': attempt_id,
                                'error': str(e)
                            })
            
            logger.info(
                f'Teacher {request.user.id} batch graded {len(results)} exams, '
                f'{len(errors)} errors'
            )
            
            return Response({
                'success_count': len(results),
                'error_count': len(errors),
                'results': results,
                'errors': errors
            })
        
        except Exception as e:
            logger.error(
                f'Error batch grading exams: {str(e)}',
                exc_info=True
            )
            return Response(
                {'error': '批量批改时发生错误'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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


class AntiCheatingBeaconView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            if isinstance(data, bytes):
                import json
                data = json.loads(data.decode('utf-8'))
            
            attempt_id = data.get('attempt_id')
            exam_id = data.get('exam_id')
            event_type = data.get('type')
            event_data = data.get('data', {})
            
            if not attempt_id:
                return Response({'status': 'ignored'}, status=status.HTTP_200_OK)
            
            try:
                attempt = ExamAttempt.objects.select_related('exam').get(id=attempt_id)
            except ExamAttempt.DoesNotExist:
                return Response({'status': 'not_found'}, status=status.HTTP_200_OK)
            
            if attempt.status not in ['in_progress', 'paused']:
                return Response({'status': 'already_submitted'}, status=status.HTTP_200_OK)
            
            self._handle_beacon_event(attempt, event_type, event_data, request)
            
            return Response({'status': 'received'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f'Beacon processing error: {str(e)}')
            return Response({'status': 'error'}, status=status.HTTP_200_OK)
    
    def _handle_beacon_event(self, attempt, event_type, event_data, request):
        from django.utils import timezone
        
        now = timezone.now()
        
        if event_type == 'before_unload':
            ExamActivityLog.objects.create(
                attempt=attempt,
                activity_type='page_unload',
                details={
                    'timestamp': event_data.get('timestamp'),
                    'ip': request.META.get('REMOTE_ADDR', 'unknown'),
                    'user_agent': request.META.get('HTTP_USER_AGENT', 'unknown')
                }
            )
        
        elif event_type == 'page_hide':
            violation_state = event_data.get('violation_state', {})
            
            ExamActivityLog.objects.create(
                attempt=attempt,
                activity_type='page_hide',
                details={
                    'timestamp': event_data.get('timestamp'),
                    'violation_state': violation_state,
                    'last_activity': event_data.get('last_activity')
                }
            )
            
            if violation_state:
                self._check_violation_threshold(attempt, violation_state)
    
    def _check_violation_threshold(self, attempt, violation_state):
        from django.utils import timezone
        
        tab_switch_count = violation_state.get('tabSwitchCount', 0)
        total_violations = violation_state.get('totalViolations', 0)
        
        max_tab_switches = attempt.exam.get_max_tab_switches()
        
        should_force_submit = False
        reason = ''
        
        if tab_switch_count >= max_tab_switches:
            should_force_submit = True
            reason = f'切出页面次数超过限制({max_tab_switches}次)'
        elif total_violations >= 10:
            should_force_submit = True
            reason = f'违规次数超过限制(10次)'
        
        if should_force_submit and attempt.status == 'in_progress':
            with transaction.atomic():
                attempt.status = 'submitted'
                attempt.submitted_manually = False
                attempt.auto_submit_reason = 'cheating'
                attempt.is_cheating_detected = True
                attempt.cheating_reason = reason
                attempt.submit_time = timezone.now()
                attempt.end_time = timezone.now()
                
                if attempt.start_time:
                    attempt.time_spent = int(
                        (attempt.end_time - attempt.start_time).total_seconds()
                    )
                
                attempt.save()
                
                CheatingRecord.objects.create(
                    attempt=attempt,
                    cheating_type='auto_submit',
                    description=reason,
                    severity='high',
                    action_taken='forced_submit'
                )
