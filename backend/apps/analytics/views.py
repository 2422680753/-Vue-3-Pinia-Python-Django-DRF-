from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Avg, Sum, F, Q, Max, Min
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from datetime import timedelta, datetime, date
import statistics
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

from .models import (
    LearningSession, DailyLearningStats, CourseProgressStats,
    LearningBehavior, LearningAnalytics, ClassAnalytics
)
from .serializers import (
    LearningSessionSerializer, DailyLearningStatsSerializer,
    CourseProgressStatsSerializer, LearningBehaviorSerializer,
    LearningAnalyticsSerializer, ClassAnalyticsSerializer,
    LearningSessionStartSerializer, LearningSessionUpdateSerializer,
    LearningBehaviorCreateSerializer
)
from apps.classes.models import Class, ClassStudent
from apps.courses.models import CourseEnrollment, Lesson
from apps.assignments.models import AssignmentSubmission
from apps.exams.models import ExamAttempt
from apps.videos.models import VideoProgress
from edu_platform.permissions import (
    IsTeacher, IsStudent, IsAdminUser, IsClassTeacher
)


class LearningSessionViewSet(viewsets.ModelViewSet):
    queryset = LearningSession.objects.select_related(
        'student', 'course', 'lesson'
    )
    serializer_class = LearningSessionSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['student', 'course', 'lesson', 'session_type', 'is_active']
    ordering_fields = ['start_time', 'duration', 'focus_score']
    ordering = ['-start_time']

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_superuser or user.role == 'admin':
            return queryset
        elif user.role == 'teacher':
            teacher_courses = CourseEnrollment.objects.filter(
                student=user,
                role='teacher',
                is_active=True
            ).values_list('course_id', flat=True)
            return queryset.filter(course_id__in=teacher_courses)
        else:
            return queryset.filter(student=user)

    @action(detail=False, methods=['post'], permission_classes=[IsStudent])
    def start(self, request):
        """开始学习会话"""
        serializer = LearningSessionStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            course_id = serializer.validated_data['course_id']
            lesson_id = serializer.validated_data.get('lesson_id')
            session_type = serializer.validated_data['session_type']
            request_id = request.data.get('request_id')
            
            from apps.courses.models import Course
            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                return Response(
                    {'error': '课程不存在'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                CourseEnrollment.objects.get_or_create(
                    student=request.user,
                    course=course,
                    defaults={'role': 'student', 'is_active': True}
                )
                
                active_sessions = LearningSession.objects.select_for_update().filter(
                    student=request.user,
                    is_active=True
                )
                
                for session in active_sessions:
                    session.is_active = False
                    session.end_time = timezone.now()
                    if session.start_time:
                        session.duration = int(
                            (session.end_time - session.start_time).total_seconds()
                        )
                    session.save()
                
                session = LearningSession.objects.create(
                    student=request.user,
                    course=course,
                    lesson_id=lesson_id,
                    session_type=session_type,
                    start_time=timezone.now(),
                    is_active=True,
                    device_info=request.META.get('HTTP_USER_AGENT', 'unknown')[:500],
                    ip_address=request.META.get('REMOTE_ADDR', 'unknown')
                )
            
            logger.info(
                f'User {request.user.id} started learning session {session.id} '
                f'for course {course_id}'
            )
            
            return Response(
                LearningSessionSerializer(session).data,
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            logger.error(
                f'Error starting learning session for user {request.user.id}: {str(e)}',
                exc_info=True
            )
            return Response(
                {'error': '开始学习会话时发生错误'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def update_session(self, request, pk=None):
        """更新学习会话"""
        session = self.get_object()
        
        try:
            if session.student != request.user:
                return Response(
                    {'error': '无权限操作此会话'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if not session.is_active:
                return Response(
                    {'error': '会话已结束，无法更新'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = LearningSessionUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            data = serializer.validated_data
            
            with transaction.atomic():
                if 'focus_score' in data:
                    session.focus_score = data['focus_score']
                if 'efficiency_score' in data:
                    session.efficiency_score = data['efficiency_score']
                if 'interactions' in data:
                    session.interactions.extend(data['interactions'][-100:])
                if 'focus_intervals' in data:
                    session.focus_intervals.extend(data['focus_intervals'][-50:])
                if 'distraction_events' in data:
                    session.distraction_events.extend(data['distraction_events'][-30:])
                
                session.save()
            
            logger.debug(
                f'User {request.user.id} updated learning session {session.id}'
            )
            
            return Response(LearningSessionSerializer(session).data)
        
        except Exception as e:
            logger.error(
                f'Error updating learning session {pk} for user {request.user.id}: {str(e)}',
                exc_info=True
            )
            return Response(
                {'error': '更新学习会话时发生错误'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def end(self, request, pk=None):
        """结束学习会话"""
        session = self.get_object()
        
        try:
            if session.student != request.user:
                return Response(
                    {'error': '无权限操作此会话'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            with transaction.atomic():
                session = LearningSession.objects.select_for_update().get(id=session.id)
                
                if not session.is_active:
                    return Response(LearningSessionSerializer(session).data)
                
                end_time = timezone.now()
                
                session.is_active = False
                session.end_time = end_time
                if session.start_time:
                    session.duration = int((end_time - session.start_time).total_seconds())
                
                if session.focus_intervals:
                    effective_seconds = sum(
                        interval.get('duration', 0) for interval in session.focus_intervals
                    )
                    session.effective_duration = effective_seconds
                
                if session.duration and session.duration > 0:
                    focus_intervals = session.focus_intervals
                    if focus_intervals:
                        avg_focus = sum(
                            interval.get('focus_score', 0.5) for interval in focus_intervals
                        ) / len(focus_intervals)
                        session.focus_score = round(avg_focus, 2)
                
                session.save()
                
                self._update_daily_stats(request.user, session)
                self._update_course_progress(request.user, session.course)
            
            logger.info(
                f'User {request.user.id} ended learning session {session.id}, '
                f'duration: {session.duration}s'
            )
            
            return Response(LearningSessionSerializer(session).data)
        
        except Exception as e:
            logger.error(
                f'Error ending learning session {pk} for user {request.user.id}: {str(e)}',
                exc_info=True
            )
            return Response(
                {'error': '结束学习会话时发生错误'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _update_daily_stats(self, user, session):
        today = timezone.now().date()
        
        daily_stats, created = DailyLearningStats.objects.get_or_create(
            student=user,
            date=today
        )
        
        daily_stats.total_sessions = F('total_sessions') + 1
        daily_stats.total_duration = F('total_duration') + (session.duration or 0)
        daily_stats.effective_duration = F('effective_duration') + (session.effective_duration or 0)
        daily_stats.courses_visited = DailyLearningStats.objects.filter(
            student=user,
            date=today
        ).values('course').distinct().count()
        
        daily_stats.save()
        
        consecutive_days = 0
        check_date = today
        while True:
            if DailyLearningStats.objects.filter(
                student=user,
                date=check_date,
                is_learning_day=True
            ).exists():
                consecutive_days += 1
                check_date -= timedelta(days=1)
            else:
                break
        
        daily_stats.streak_days = consecutive_days
        daily_stats.is_learning_day = daily_stats.total_sessions > 0
        daily_stats.save()

    def _update_course_progress(self, user, course):
        enrollment = CourseEnrollment.objects.filter(
            student=user,
            course=course,
            is_active=True
        ).first()
        
        if not enrollment:
            return
        
        progress_stats, created = CourseProgressStats.objects.get_or_create(
            student=user,
            course=course,
            enrollment=enrollment
        )
        
        total_lessons = Lesson.objects.filter(
            chapter__course=course,
            is_published=True
        ).count()
        
        completed_lessons = VideoProgress.objects.filter(
            video__lesson__chapter__course=course,
            user=user,
            progress__gte=1.0
        ).count()
        
        progress_stats.total_lessons = total_lessons
        progress_stats.completed_lessons = completed_lessons
        
        total_sessions = LearningSession.objects.filter(
            student=user,
            course=course
        )
        progress_stats.total_study_time = total_sessions.aggregate(
            total=Sum('duration')
        )['total'] or 0
        
        if total_lessons > 0:
            progress_stats.overall_progress = completed_lessons / total_lessons
        progress_stats.last_access_at = timezone.now()
        
        if not progress_stats.first_access_at:
            progress_stats.first_access_at = timezone.now()
        
        progress_stats.save()


class DailyLearningStatsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailyLearningStats.objects.select_related('student')
    serializer_class = DailyLearningStatsSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['student', 'date', 'is_learning_day']
    ordering_fields = ['date', 'total_duration', 'streak_days']
    ordering = ['-date']

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_superuser or user.role == 'admin':
            return queryset
        elif user.role == 'teacher':
            return queryset
        else:
            return queryset.filter(student=user)

    @action(detail=False, methods=['get'])
    def my_stats(self, request):
        days = request.query_params.get('days', 30)
        try:
            days = int(days)
        except (ValueError, TypeError):
            days = 30
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        stats = DailyLearningStats.objects.filter(
            student=request.user,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        return Response(DailyLearningStatsSerializer(stats, many=True).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        days = request.query_params.get('days', 30)
        try:
            days = int(days)
        except (ValueError, TypeError):
            days = 30
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        stats = DailyLearningStats.objects.filter(
            student=request.user,
            date__range=[start_date, end_date]
        )
        
        total_days = stats.count()
        learning_days = stats.filter(is_learning_day=True).count()
        
        agg = stats.aggregate(
            total_duration=Sum('total_duration'),
            total_effective=Sum('effective_duration'),
            total_sessions=Sum('total_sessions'),
            total_lessons=Sum('lessons_completed'),
            avg_focus=Avg('average_focus_score'),
            max_streak=Max('streak_days')
        )
        
        current_streak = 0
        check_date = end_date
        while True:
            if stats.filter(date=check_date, is_learning_day=True).exists():
                current_streak += 1
                check_date -= timedelta(days=1)
            else:
                break
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'summary': {
                'total_days': total_days,
                'learning_days': learning_days,
                'total_sessions': agg['total_sessions'] or 0,
                'total_duration': agg['total_duration'] or 0,
                'total_effective_duration': agg['total_effective'] or 0,
                'total_lessons_completed': agg['total_lessons'] or 0,
                'average_focus_score': agg['avg_focus'],
                'current_streak': current_streak,
                'max_streak': agg['max_streak'] or 0
            },
            'average_per_learning_day': {
                'sessions': (agg['total_sessions'] or 0) / learning_days if learning_days else 0,
                'duration': (agg['total_duration'] or 0) / learning_days if learning_days else 0,
                'effective_duration': (agg['total_effective'] or 0) / learning_days if learning_days else 0
            }
        })


class CourseProgressStatsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CourseProgressStats.objects.select_related(
        'student', 'course', 'enrollment'
    )
    serializer_class = CourseProgressStatsSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['student', 'course', 'overall_progress']
    ordering_fields = ['overall_progress', 'last_access_at', 'total_study_time']
    ordering = ['-last_access_at']

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_superuser or user.role == 'admin':
            return queryset
        elif user.role == 'teacher':
            teacher_courses = CourseEnrollment.objects.filter(
                student=user,
                role='teacher',
                is_active=True
            ).values_list('course_id', flat=True)
            return queryset.filter(course_id__in=teacher_courses)
        else:
            return queryset.filter(student=user)

    @action(detail=False, methods=['get'])
    def my_progress(self, request):
        progress = self.get_queryset().filter(student=request.user)
        return Response(CourseProgressStatsSerializer(progress, many=True).data)

    @action(detail=True, methods=['get'])
    def detailed(self, request, pk=None):
        progress = self.get_object()
        
        chapters = []
        from apps.courses.models import Chapter, Lesson
        from apps.videos.models import VideoProgress
        
        chapter_list = Chapter.objects.filter(
            course=progress.course
        ).prefetch_related('lessons')
        
        for chapter in chapter_list:
            lessons = []
            for lesson in chapter.lessons.filter(is_published=True):
                video_progress = VideoProgress.objects.filter(
                    video__lesson=lesson,
                    user=request.user
                ).first()
                
                lessons.append({
                    'id': lesson.id,
                    'title': lesson.title,
                    'progress': video_progress.progress if video_progress else 0,
                    'last_watched': video_progress.last_watched_at if video_progress else None,
                    'is_completed': video_progress.progress >= 1.0 if video_progress else False
                })
            
            total_lessons = len(lessons)
            completed_lessons = sum(1 for l in lessons if l['is_completed'])
            
            chapters.append({
                'id': chapter.id,
                'title': chapter.title,
                'order': chapter.order,
                'total_lessons': total_lessons,
                'completed_lessons': completed_lessons,
                'progress': completed_lessons / total_lessons if total_lessons else 0,
                'lessons': lessons
            })
        
        base_data = CourseProgressStatsSerializer(progress).data
        base_data['chapters'] = chapters
        
        return Response(base_data)


class LearningBehaviorViewSet(viewsets.ModelViewSet):
    queryset = LearningBehavior.objects.select_related(
        'student', 'course', 'lesson'
    )
    serializer_class = LearningBehaviorSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['student', 'course', 'lesson', 'behavior_type', 'session_id']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

    def get_permissions(self):
        if self.action == 'create':
            return [IsStudent()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_superuser or user.role == 'admin':
            return queryset
        elif user.role == 'teacher':
            return queryset
        else:
            return queryset.filter(student=user)

    @action(detail=False, methods=['post'])
    def record(self, request):
        serializer = LearningBehaviorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        course_id = serializer.validated_data['course_id']
        lesson_id = serializer.validated_data.get('lesson_id')
        behavior_type = serializer.validated_data['behavior_type']
        details = serializer.validated_data.get('details', {})
        session_id = serializer.validated_data.get('session_id')
        
        from apps.courses.models import Course
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {'error': '课程不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        LearningBehavior.objects.create(
            student=request.user,
            course=course,
            lesson_id=lesson_id,
            behavior_type=behavior_type,
            details=details,
            session_id=session_id
        )
        
        return Response({'message': '行为记录成功'})

    @action(detail=False, methods=['get'])
    def analysis(self, request):
        days = request.query_params.get('days', 14)
        try:
            days = int(days)
        except (ValueError, TypeError):
            days = 14
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        behaviors = LearningBehavior.objects.filter(
            student=request.user,
            timestamp__range=[start_date, end_date]
        )
        
        behavior_counts = behaviors.values('behavior_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        daily_counts = behaviors.annotate(
            date=TruncDate('timestamp')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        hour_distribution = defaultdict(int)
        for behavior in behaviors:
            hour = behavior.timestamp.hour
            hour_distribution[hour] += 1
        
        weekday_distribution = defaultdict(int)
        for behavior in behaviors:
            weekday = behavior.timestamp.weekday()
            weekday_distribution[weekday] += 1
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'behavior_types': [
                {'type': bc['behavior_type'], 'count': bc['count']
                for bc in behavior_counts
            ],
            'daily_activity': [
                {'date': str(dc['date']), 'count': dc['count']
                for dc in daily_counts
            ],
            'hour_distribution': dict(hour_distribution),
            'weekday_distribution': dict(weekday_distribution)
        })


class LearningAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LearningAnalytics.objects.select_related(
        'student', 'course'
    )
    serializer_class = LearningAnalyticsSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['student', 'course', 'analysis_date', 'dropout_risk']
    ordering_fields = ['analysis_date', 'overall_engagement_score']
    ordering = ['-analysis_date']

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_superuser or user.role == 'admin':
            return queryset
        elif user.role == 'teacher':
            return queryset
        else:
            return queryset.filter(student=user)

    @action(detail=False, methods=['get'])
    def my_analytics(self, request):
        course_id = request.query_params.get('course_id')
        
        queryset = self.get_queryset().filter(student=request.user)
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        latest = queryset.order_by('-analysis_date').first()
        
        if not latest:
            return Response({
                'message': '暂无学习分析数据'
            })
        
        return Response(LearningAnalyticsSerializer(latest).data)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        user = request.user
        today = timezone.now().date()
        
        enrollments = CourseEnrollment.objects.filter(
            student=user,
            is_active=True
        )
        
        course_progresses = CourseProgressStats.objects.filter(
            student=user
        )
        
        sessions_30d = LearningSession.objects.filter(
            student=user,
            start_time__gte=today - timedelta(days=30)
        )
        
        daily_stats = DailyLearningStats.objects.filter(
            student=user,
            date__range=[today - timedelta(days=30), today]
        )
        
        learning_days = daily_stats.filter(is_learning_day=True).count()
        
        current_streak = 0
        check_date = today
        while True:
            if daily_stats.filter(date=check_date, is_learning_day=True).exists():
                current_streak += 1
                check_date -= timedelta(days=1)
            else:
                break
        
        total_duration = sessions_30d.aggregate(total=Sum('duration'))['total'] or 0
        effective_duration = sessions_30d.aggregate(total=Sum('effective_duration'))['total'] or 0
        
        avg_focus = sessions_30d.exclude(
            focus_score__isnull=True
        ).aggregate(avg=Avg('focus_score'))['avg']
        
        behaviors = LearningBehavior.objects.filter(
            student=user,
            timestamp__gte=today - timedelta(days=7)
        )
        
        hour_distribution = defaultdict(int)
        for behavior in behaviors:
            hour = behavior.timestamp.hour
            hour_distribution[hour] += 1
        
        peak_hours = []
        if hour_distribution:
            max_count = max(hour_distribution.values())
            peak_hours = [h for h, c in hour_distribution.items() if c == max_count]
        
        submission_stats = AssignmentSubmission.objects.filter(
            student=user
        ).aggregate(
            total=Count('id'),
            submitted=Count('id', filter=Q(submitted_at__isnull=False)),
            on_time=Count('id', filter=Q(
                submitted_at__isnull=False,
                submitted_at__lte=F('assignment__due_date')
            ))
        )
        
        exam_stats = ExamAttempt.objects.filter(
            student=user,
            status='graded'
        ).aggregate(
            total=Count('id'),
            passed=Count('id', filter=Q(is_passed=True)),
            avg_score=Avg('total_score')
        )
        
        return Response({
            'overview': {
                'active_courses': enrollments.count(),
                'learning_days_last_30d': learning_days,
                'current_streak': current_streak,
                'total_study_time_last_30d': total_duration,
                'effective_study_time_last_30d': effective_duration,
                'average_focus_score': avg_focus
            },
            'course_progress': [
                {
                    'course_id': cp.course_id,
                    'course_title': cp.course.title,
                    'progress': cp.overall_progress,
                    'completed_lessons': cp.completed_lessons,
                    'total_lessons': cp.total_lessons,
                    'total_study_time': cp.total_study_time
                }
                for cp in course_progresses
            ],
            'learning_pattern': {
                'peak_hours': peak_hours,
                'hour_distribution': dict(hour_distribution)
            },
            'performance': {
                'assignments': {
                    'total': submission_stats['total'],
                    'submitted': submission_stats['submitted'],
                    'on_time_rate': submission_stats['on_time'] / submission_stats['submitted'] if submission_stats['submitted'] else 0
                },
                'exams': {
                    'total': exam_stats['total'],
                    'passed': exam_stats['passed'],
                    'pass_rate': exam_stats['passed'] / exam_stats['total'] if exam_stats['total'] else 0,
                    'average_score': float(exam_stats['avg_score']) if exam_stats['avg_score'] else None
                }
            }
        })


class ClassAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ClassAnalytics.objects.select_related('class_obj')
    serializer_class = ClassAnalyticsSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['class_obj', 'analysis_date']
    ordering_fields = ['analysis_date']
    ordering = ['-analysis_date']

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_superuser or user.role == 'admin':
            return queryset
        elif user.role == 'teacher':
            teacher_classes = Class.objects.filter(
                Q(teacher=user) | Q(assistant_teachers=user)
            ).values_list('id', flat=True)
            return queryset.filter(class_obj_id__in=teacher_classes)
        else:
            student_classes = ClassStudent.objects.filter(
                student=user,
                is_active=True
            ).values_list('class_obj_id', flat=True)
            return queryset.filter(class_obj_id__in=student_classes)

    @action(detail=True, methods=['get'], permission_classes=[IsClassTeacher | IsAdminUser])
    def detailed(self, request, pk=None):
        class_analytics = self.get_object()
        class_obj = class_analytics.class_obj
        
        class_students = ClassStudent.objects.filter(
            class_obj=class_obj,
            is_active=True
        ).select_related('student')
        
        student_ids = class_students.values_list('student_id', flat=True)
        
        course = class_obj.course
        
        progress_stats = CourseProgressStats.objects.filter(
            student_id__in=student_ids,
            course=course
        )
        
        avg_progress = progress_stats.aggregate(
            avg=Avg('overall_progress')
        )['avg'] or 0
        
        progress_distribution = {
            'excellent': progress_stats.filter(overall_progress__gte=0.8).count(),
            'good': progress_stats.filter(overall_progress__gte=0.6, overall_progress__lt=0.8).count(),
            'fair': progress_stats.filter(overall_progress__gte=0.4, overall_progress__lt=0.6).count(),
            'poor': progress_stats.filter(overall_progress__lt=0.4).count()
        }
        
        submissions = AssignmentSubmission.objects.filter(
            student_id__in=student_ids,
            assignment__course=course
        )
        
        submission_stats = submissions.aggregate(
            total=Count('id'),
            submitted=Count('id', filter=Q(submitted_at__isnull=False)),
            on_time=Count('id', filter=Q(
                submitted_at__isnull=False,
                submitted_at__lte=F('assignment__due_date')
            )),
            avg_score=Avg('total_score', filter=Q(
                status='graded',
                total_score__isnull=False
            ))
        )
        
        exam_attempts = ExamAttempt.objects.filter(
            student_id__in=student_ids,
            exam__course=course,
            status='graded'
        )
        
        exam_stats = exam_attempts.aggregate(
            total=Count('id'),
            passed=Count('id', filter=Q(is_passed=True)),
            avg_score=Avg('total_score')
        )
        
        score_distribution = {
            'excellent': exam_attempts.filter(total_score__gte=90).count(),
            'good': exam_attempts.filter(total_score__gte=80, total_score__lt=90).count(),
            'pass': exam_attempts.filter(total_score__gte=60, total_score__lt=80).count(),
            'fail': exam_attempts.filter(total_score__lt=60).count()
        }
        
        learning_sessions = LearningSession.objects.filter(
            student_id__in=student_ids,
            course=course,
            start_time__gte=timezone.now() - timedelta(days=30)
        )
        
        total_study_time = learning_sessions.aggregate(
            total=Sum('duration')
        )['total'] or 0
        
        weekly_activity = learning_sessions.annotate(
            week=TruncWeek('start_time')
        ).values('week').annotate(
            sessions=Count('id'),
            duration=Sum('duration')
        ).order_by('week')
        
        attendance_rates = class_students.values_list('attendance_rate', flat=True)
        avg_attendance = sum(attendance_rates) / len(attendance_rates) if attendance_rates else 0
        
        at_risk_students = []
        for cs in class_students:
            progress = progress_stats.filter(student=cs.student).first()
            risk_factors = 0
            
            if progress:
                if progress.overall_progress < 0.4:
                    risk_factors += 1
                if progress.assignments_average_score and progress.assignments_average_score < 60:
                    risk_factors += 1
            
            if cs.attendance_rate < 0.7:
                risk_factors += 1
            
            if risk_factors >= 2:
                at_risk_students.append({
                    'student_id': cs.student_id,
                    'student_name': cs.student.get_full_name() or cs.student.username,
                    'progress': progress.overall_progress if progress else 0,
                    'attendance_rate': cs.attendance_rate,
                    'risk_factors': risk_factors
                })
        
        return Response({
            'class_info': {
                'id': class_obj.id,
                'name': class_obj.name,
                'code': class_obj.code,
                'total_students': class_students.count()
            },
            'overview': {
                'average_progress': avg_progress,
                'average_attendance_rate': avg_attendance,
                'total_study_time_last_30d': total_study_time,
                'at_risk_student_count': len(at_risk_students)
            },
            'progress_distribution': progress_distribution,
            'submission_stats': {
                'total': submission_stats['total'],
                'submission_rate': submission_stats['submitted'] / submission_stats['total'] if submission_stats['total'] else 0,
                'on_time_rate': submission_stats['on_time'] / submission_stats['submitted'] if submission_stats['submitted'] else 0,
                'average_score': float(submission_stats['avg_score']) if submission_stats['avg_score'] else None
            },
            'exam_stats': {
                'total': exam_stats['total'],
                'pass_rate': exam_stats['passed'] / exam_stats['total'] if exam_stats['total'] else 0,
                'average_score': float(exam_stats['avg_score']) if exam_stats['avg_score'] else None,
                'score_distribution': score_distribution
            },
            'weekly_activity': [
                {
                    'week': str(wa['week']),
                    'sessions': wa['sessions'],
                    'duration': wa['duration']
                }
                for wa in weekly_activity
            ],
            'at_risk_students': at_risk_students
        })

    @action(detail=False, methods=['get'])
    def teacher_dashboard(self, request):
        user = request.user
        
        if user.role not in ['teacher', 'admin'] and not user.is_superuser:
            return Response(
                {'error': '无权限访问'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        teacher_classes = Class.objects.filter(
            Q(teacher=user) | Q(assistant_teachers=user)
        ).prefetch_related('students')
        
        total_students = 0
        active_students = 0
        
        for class_obj in teacher_classes:
            total_students += class_obj.students.filter(is_active=True).count()
            
            active_ids = LearningSession.objects.filter(
                student__class_enrollments__class_obj=class_obj,
                student__class_enrollments__is_active=True,
                start_time__gte=timezone.now() - timedelta(days=7)
            ).values_list('student_id', flat=True).distinct()
            
            active_students += len(active_ids)
        
        class_list = []
        for class_obj in teacher_classes:
            class_students = class_obj.students.filter(is_active=True)
            student_ids = class_students.values_list('student_id', flat=True)
            
            progress_stats = CourseProgressStats.objects.filter(
                student_id__in=student_ids,
                course=class_obj.course
            )
            
            avg_progress = progress_stats.aggregate(
                avg=Avg('overall_progress')
            )['avg'] or 0
            
            attendance_rates = class_students.values_list('attendance_rate', flat=True)
            avg_attendance = sum(attendance_rates) / len(attendance_rates) if attendance_rates else 0
            
            class_list.append({
                'id': class_obj.id,
                'name': class_obj.name,
                'code': class_obj.code,
                'status': class_obj.status,
                'start_date': class_obj.start_date,
                'end_date': class_obj.end_date,
                'total_students': class_students.count(),
                'average_progress': avg_progress,
                'average_attendance': avg_attendance
            })
        
        return Response({
            'overview': {
                'total_classes': teacher_classes.count(),
                'total_students': total_students,
                'active_students_last_7d': active_students
            },
            'classes': class_list
        })
