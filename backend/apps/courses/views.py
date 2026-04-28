from rest_framework import generics, viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q, Avg, Count

from .models import (
    Category, Tag, Course, Chapter, Lesson,
    CourseEnrollment, CourseReview, LiveCourse, LiveChatMessage
)
from .serializers import (
    CategorySerializer, TagSerializer, CourseListSerializer,
    CourseDetailSerializer, CourseCreateSerializer, ChapterSerializer,
    ChapterCreateSerializer, LessonSerializer, LessonCreateSerializer,
    CourseEnrollmentSerializer, CourseReviewSerializer,
    CourseReviewCreateSerializer, LiveCourseSerializer,
    LiveChatMessageSerializer
)
from edu_platform.permissions import (
    IsAdminUser, IsTeacher, IsStudent, IsCourseInstructor,
    IsCourseStudent, CanEditCourse
)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(parent=None, is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [SearchFilter]
    search_fields = ['name', 'description']

    @action(detail=False, methods=['get'])
    def all(self, request):
        categories = Category.objects.filter(is_active=True).order_by('sort_order')
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.AllowAny]


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.select_related(
        'instructor', 'category'
    ).prefetch_related(
        'tags', 'chapters', 'reviews'
    ).annotate(
        average_rating=Avg('reviews__rating'),
        review_count=Count('reviews')
    )
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['course_type', 'level', 'status', 'is_featured', 'is_free', 'category']
    search_fields = ['title', 'short_description', 'description']
    ordering_fields = ['created_at', 'price', 'total_students', 'average_rating']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return CourseCreateSerializer
        return CourseDetailSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsTeacher | IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [p() for p in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in ['list', 'retrieve']:
            if not self.request.user.is_authenticated or (
                not self.request.user.is_teacher and 
                not self.request.user.is_admin and 
                not self.request.user.is_superuser
            ):
                return queryset.filter(status='published')
        return queryset

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def enroll(self, request, pk=None):
        course = self.get_object()
        
        if CourseEnrollment.objects.filter(course=course, student=request.user, is_active=True).exists():
            return Response(
                {'error': '您已报名该课程'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if course.price > 0 and not course.is_free:
            return Response(
                {'error': '该课程需要付费，请先完成支付'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        enrollment = CourseEnrollment.objects.create(
            course=course,
            student=request.user,
            enrollment_type='free',
            price_paid=0
        )
        
        return Response(
            CourseEnrollmentSerializer(enrollment).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['get'], permission_classes=[IsCourseStudent])
    def my_progress(self, request, pk=None):
        course = self.get_object()
        enrollment = CourseEnrollment.objects.filter(
            course=course, student=request.user
        ).first()
        
        if not enrollment:
            return Response(
                {'error': '您未报名该课程'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(CourseEnrollmentSerializer(enrollment).data)

    @action(detail=True, methods=['get'])
    def chapters(self, request, pk=None):
        course = self.get_object()
        chapters = course.chapters.order_by('chapter_order')
        serializer = ChapterSerializer(
            chapters, 
            many=True, 
            context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        course = self.get_object()
        reviews = course.reviews.select_related('student').order_by('-created_at')
        
        page = self.paginate_queryset(reviews)
        if page is not None:
            serializer = CourseReviewSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CourseReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def write_review(self, request, pk=None):
        course = self.get_object()
        serializer = CourseReviewCreateSerializer(
            data=request.data,
            context={'request': request, 'course': course}
        )
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        
        return Response(
            CourseReviewSerializer(review).data,
            status=status.HTTP_201_CREATED
        )


class ChapterViewSet(viewsets.ModelViewSet):
    queryset = Chapter.objects.select_related('course').prefetch_related('lessons')
    serializer_class = ChapterSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['course']
    ordering_fields = ['chapter_order', 'created_at']
    ordering = ['chapter_order']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ChapterCreateSerializer
        return ChapterSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsCourseInstructor | IsAdminUser]
        return [p() for p in permission_classes]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class LessonViewSet(viewsets.ModelViewSet):
    queryset = Lesson.objects.select_related(
        'chapter', 'chapter__course'
    )
    serializer_class = LessonSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['chapter', 'chapter__course']
    ordering_fields = ['lesson_order', 'created_at']
    ordering = ['lesson_order']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return LessonCreateSerializer
        return LessonSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsCourseInstructor | IsAdminUser]
        return [p() for p in permission_classes]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def next(self, request, pk=None):
        lesson = self.get_object()
        next_lesson = Lesson.objects.filter(
            chapter=lesson.chapter,
            lesson_order__gt=lesson.lesson_order
        ).order_by('lesson_order').first()
        
        if not next_lesson:
            next_chapter = Chapter.objects.filter(
                course=lesson.chapter.course,
                chapter_order__gt=lesson.chapter.chapter_order
            ).order_by('chapter_order').first()
            
            if next_chapter:
                next_lesson = next_chapter.lessons.order_by('lesson_order').first()
        
        if next_lesson:
            return Response(LessonSerializer(next_lesson, context={'request': request}).data)
        return Response({'message': '这是最后一个课时'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def previous(self, request, pk=None):
        lesson = self.get_object()
        prev_lesson = Lesson.objects.filter(
            chapter=lesson.chapter,
            lesson_order__lt=lesson.lesson_order
        ).order_by('-lesson_order').first()
        
        if not prev_lesson:
            prev_chapter = Chapter.objects.filter(
                course=lesson.chapter.course,
                chapter_order__lt=lesson.chapter.chapter_order
            ).order_by('-chapter_order').first()
            
            if prev_chapter:
                prev_lesson = prev_chapter.lessons.order_by('-lesson_order').first()
        
        if prev_lesson:
            return Response(LessonSerializer(prev_lesson, context={'request': request}).data)
        return Response({'message': '这是第一个课时'}, status=status.HTTP_404_NOT_FOUND)


class MyCoursesView(generics.ListAPIView):
    serializer_class = CourseListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        enrollments = CourseEnrollment.objects.filter(
            student=self.request.user,
            is_active=True
        ).select_related('course')
        
        course_ids = [e.course_id for e in enrollments]
        
        return Course.objects.filter(id__in=course_ids).annotate(
            average_rating=Avg('reviews__rating'),
            review_count=Count('reviews')
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        in_progress = []
        completed = []
        
        for course in queryset:
            enrollment = CourseEnrollment.objects.filter(
                course=course, student=request.user
            ).first()
            course_data = CourseListSerializer(course, context={'request': request}).data
            
            if enrollment:
                course_data['progress'] = enrollment.progress
                course_data['is_completed'] = enrollment.is_completed
                
                if enrollment.is_completed:
                    completed.append(course_data)
                else:
                    in_progress.append(course_data)
        
        return Response({
            'in_progress': in_progress,
            'completed': completed
        })


class LiveCourseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LiveCourse.objects.select_related(
        'course', 'instructor'
    ).order_by('-start_time')
    serializer_class = LiveCourseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['course', 'status']
    ordering_fields = ['start_time']

    @action(detail=True, methods=['post'], permission_classes=[IsTeacher])
    def start(self, request, pk=None):
        live_course = self.get_object()
        if live_course.status != 'scheduled':
            return Response(
                {'error': '直播状态不正确'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        live_course.status = 'live'
        live_course.save()
        
        return Response(self.get_serializer(live_course).data)

    @action(detail=True, methods=['post'], permission_classes=[IsTeacher])
    def end(self, request, pk=None):
        live_course = self.get_object()
        if live_course.status != 'live':
            return Response(
                {'error': '直播未在进行中'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        live_course.status = 'ended'
        live_course.save()
        
        return Response(self.get_serializer(live_course).data)
