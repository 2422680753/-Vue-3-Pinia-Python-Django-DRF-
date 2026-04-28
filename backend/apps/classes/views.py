import uuid
from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Avg, Q

from .models import (
    Class, ClassStudent, ClassSchedule, ClassAttendance,
    ClassAnnouncement, ClassMaterial, ClassStatus
)
from .serializers import (
    ClassListSerializer, ClassDetailSerializer, ClassCreateSerializer,
    ClassStudentSerializer, ClassStudentListSerializer,
    ClassScheduleSerializer, ClassAttendanceSerializer,
    ClassAttendanceBulkSerializer, ClassAnnouncementSerializer,
    ClassMaterialSerializer, ClassGradeSerializer,
    ClassGraduateSerializer, JoinClassSerializer
)
from apps.courses.models import CourseEnrollment
from edu_platform.permissions import (
    IsTeacher, IsStudent, IsAdminUser, IsClassTeacher
)


def generate_join_code():
    code = uuid.uuid4().hex[:8].upper()
    while Class.objects.filter(join_code=code).exists():
        code = uuid.uuid4().hex[:8].upper()
    return code


class ClassViewSet(viewsets.ModelViewSet):
    queryset = Class.objects.select_related(
        'course', 'teacher'
    ).prefetch_related(
        'assistant_teachers', 'students', 'schedules',
        'announcements', 'materials'
    )
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['course', 'teacher', 'status', 'is_private']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['created_at', 'start_date', 'end_date', 'current_students']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return ClassListSerializer
        elif self.action == 'retrieve':
            return ClassDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ClassCreateSerializer
        return ClassDetailSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['create']:
            permission_classes = [IsTeacher | IsAdminUser]
        else:
            permission_classes = [IsClassTeacher | IsAdminUser]
        return [p() for p in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_superuser or user.role == 'admin':
            return queryset
        elif user.role == 'teacher':
            return queryset.filter(
                Q(teacher=user) | Q(assistant_teachers=user)
            ).distinct()
        else:
            class_ids = ClassStudent.objects.filter(
                student=user,
                is_active=True
            ).values_list('class_obj_id', flat=True)
            return queryset.filter(id__in=class_ids)

    def perform_create(self, serializer):
        code = f'CLS{uuid.uuid4().hex[:6].upper()}'
        while Class.objects.filter(code=code).exists():
            code = f'CLS{uuid.uuid4().hex[:6].upper()}'
        
        instance = serializer.save(
            code=code,
            join_code=generate_join_code() if serializer.validated_data.get('is_private') else None
        )
        
        if instance.teacher and instance.course:
            CourseEnrollment.objects.get_or_create(
                student=instance.teacher,
                course=instance.course,
                defaults={'role': 'teacher', 'is_active': True}
            )

    @action(detail=False, methods=['get'])
    def my_classes(self, request):
        user = request.user
        classes = self.get_queryset()
        
        now = timezone.now().date()
        
        upcoming = classes.filter(status=ClassStatus.UPCOMING)
        active = classes.filter(status=ClassStatus.ACTIVE)
        completed = classes.filter(status__in=[ClassStatus.COMPLETED, ClassStatus.ARCHIVED])
        
        return Response({
            'upcoming': ClassListSerializer(upcoming, many=True).data,
            'active': ClassListSerializer(active, many=True).data,
            'completed': ClassListSerializer(completed, many=True).data,
        })

    @action(detail=True, methods=['post'])
    def regenerate_join_code(self, request, pk=None):
        class_obj = self.get_object()
        class_obj.join_code = generate_join_code()
        class_obj.save()
        
        return Response({'join_code': class_obj.join_code})

    @action(detail=False, methods=['post'], permission_classes=[IsStudent])
    def join(self, request):
        serializer = JoinClassSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        join_code = serializer.validated_data.get('join_code')
        
        try:
            class_obj = Class.objects.get(join_code=join_code)
        except Class.DoesNotExist:
            return Response(
                {'error': '加入码无效'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if class_obj.current_students >= class_obj.max_students:
            return Response(
                {'error': '班级人数已满'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        existing = ClassStudent.objects.filter(
            class_obj=class_obj,
            student=request.user
        ).first()
        
        if existing:
            if existing.is_active:
                return Response(
                    {'error': '您已在该班级中'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                existing.is_active = True
                existing.dropped_at = None
                existing.drop_reason = None
                existing.save()
                return Response(ClassStudentSerializer(existing).data)
        
        with transaction.atomic():
            CourseEnrollment.objects.get_or_create(
                student=request.user,
                course=class_obj.course,
                defaults={'role': 'student', 'is_active': True}
            )
            
            class_student = ClassStudent.objects.create(
                class_obj=class_obj,
                student=request.user,
                join_type='code'
            )
            
            class_obj.current_students = class_obj.students.filter(is_active=True).count()
            class_obj.save()
        
        return Response(
            ClassStudentSerializer(class_student).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsClassTeacher | IsAdminUser])
    def add_student(self, request, pk=None):
        class_obj = self.get_object()
        student_id = request.data.get('student_id')
        
        if class_obj.current_students >= class_obj.max_students:
            return Response(
                {'error': '班级人数已满'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from apps.users.models import User
        try:
            student = User.objects.get(id=student_id)
        except User.DoesNotExist:
            return Response(
                {'error': '用户不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        existing = ClassStudent.objects.filter(
            class_obj=class_obj,
            student=student
        ).first()
        
        if existing and existing.is_active:
            return Response(
                {'error': '该学生已在班级中'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            CourseEnrollment.objects.get_or_create(
                student=student,
                course=class_obj.course,
                defaults={'role': 'student', 'is_active': True}
            )
            
            if existing:
                existing.is_active = True
                existing.dropped_at = None
                existing.drop_reason = None
                existing.save()
            else:
                ClassStudent.objects.create(
                    class_obj=class_obj,
                    student=student,
                    join_type='admin'
                )
            
            class_obj.current_students = class_obj.students.filter(is_active=True).count()
            class_obj.save()
        
        return Response({'message': '学生添加成功'})

    @action(detail=True, methods=['post'], permission_classes=[IsClassTeacher | IsAdminUser])
    def remove_student(self, request, pk=None):
        class_obj = self.get_object()
        student_id = request.data.get('student_id')
        reason = request.data.get('reason', '')
        
        try:
            class_student = ClassStudent.objects.get(
                class_obj=class_obj,
                student_id=student_id,
                is_active=True
            )
        except ClassStudent.DoesNotExist:
            return Response(
                {'error': '该学生不在班级中'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        class_student.is_active = False
        class_student.dropped_at = timezone.now()
        class_student.drop_reason = reason
        class_student.save()
        
        class_obj.current_students = class_obj.students.filter(is_active=True).count()
        class_obj.save()
        
        return Response({'message': '学生已移出班级'})

    @action(detail=True, methods=['post'], permission_classes=[IsClassTeacher | IsAdminUser])
    def set_grade(self, request, pk=None):
        class_obj = self.get_object()
        serializer = ClassGradeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        student_id = serializer.validated_data['student_id']
        final_grade = serializer.validated_data['final_grade']
        notes = serializer.validated_data.get('notes')
        
        try:
            class_student = ClassStudent.objects.get(
                class_obj=class_obj,
                student_id=student_id
            )
        except ClassStudent.DoesNotExist:
            return Response(
                {'error': '该学生不在班级中'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        class_student.final_grade = final_grade
        if notes is not None:
            class_student.notes = notes
        class_student.save()
        
        return Response(ClassStudentSerializer(class_student).data)

    @action(detail=True, methods=['post'], permission_classes=[IsClassTeacher | IsAdminUser])
    def graduate(self, request, pk=None):
        class_obj = self.get_object()
        serializer = ClassGraduateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        student_ids = serializer.validated_data['student_ids']
        final_grade = serializer.validated_data.get('final_grade')
        notes = serializer.validated_data.get('notes')
        
        class_students = ClassStudent.objects.filter(
            class_obj=class_obj,
            student_id__in=student_ids,
            is_active=True
        )
        
        graduated_count = 0
        for cs in class_students:
            cs.is_graduated = True
            cs.graduated_at = timezone.now()
            if final_grade is not None:
                cs.final_grade = final_grade
            if notes is not None:
                cs.notes = notes
            cs.save()
            graduated_count += 1
        
        return Response({
            'message': f'成功结业 {graduated_count} 名学生'
        })

    @action(detail=True, methods=['get'], permission_classes=[IsClassTeacher | IsAdminUser])
    def stats(self, request, pk=None):
        class_obj = self.get_object()
        
        students = class_obj.students.filter(is_active=True)
        total_students = students.count()
        
        attendance_records = ClassAttendance.objects.filter(
            schedule__class_obj=class_obj,
            student__in=[s.student for s in students]
        )
        
        total_attendances = attendance_records.count()
        present_count = attendance_records.filter(status='present').count()
        absent_count = attendance_records.filter(status='absent').count()
        late_count = attendance_records.filter(status='late').count()
        
        avg_attendance_rate = students.aggregate(avg=Avg('attendance_rate'))['avg'] or 0
        
        graded_students = students.exclude(final_grade__isnull=True)
        avg_grade = graded_students.aggregate(avg=Avg('final_grade'))['avg'] if graded_students.exists() else None
        
        graded_count = graded_students.count()
        pass_count = graded_students.filter(final_grade__gte=60).count()
        pass_rate = pass_count / graded_count if graded_count > 0 else 0
        
        graduated_count = students.filter(is_graduated=True).count()
        
        return Response({
            'total_students': total_students,
            'current_students': class_obj.current_students,
            'max_students': class_obj.max_students,
            
            'attendance_stats': {
                'total_records': total_attendances,
                'present_count': present_count,
                'absent_count': absent_count,
                'late_count': late_count,
                'average_attendance_rate': round(avg_attendance_rate * 100, 2)
            },
            
            'grade_stats': {
                'graded_count': graded_count,
                'pass_count': pass_count,
                'fail_count': graded_count - pass_count,
                'pass_rate': round(pass_rate * 100, 2),
                'average_grade': float(avg_grade) if avg_grade else None,
                'graduated_count': graduated_count
            },
            
            'schedule_count': class_obj.schedules.filter(is_active=True).count(),
            'announcement_count': class_obj.announcements.filter(is_draft=False).count(),
            'material_count': class_obj.materials.count()
        })


class ClassStudentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ClassStudent.objects.select_related(
        'class_obj', 'student'
    )
    serializer_class = ClassStudentSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['class_obj', 'is_active', 'is_graduated']
    ordering_fields = ['enrolled_at', 'final_grade', 'attendance_rate']
    ordering = ['-enrolled_at']

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
            return queryset.filter(student=user)

    @action(detail=False, methods=['get'])
    def my_enrollments(self, request):
        enrollments = self.get_queryset().filter(student=request.user)
        return Response(ClassStudentListSerializer(enrollments, many=True).data)


class ClassScheduleViewSet(viewsets.ModelViewSet):
    queryset = ClassSchedule.objects.select_related(
        'class_obj', 'teacher', 'lesson'
    ).prefetch_related(
        'attendances'
    )
    serializer_class = ClassScheduleSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['class_obj', 'day_of_week', 'is_recurring', 'is_active']
    ordering_fields = ['day_of_week', 'start_time', 'start_date']
    ordering = ['day_of_week', 'start_time']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsClassTeacher | IsAdminUser]
        return [p() for p in permission_classes]

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

    @action(detail=True, methods=['post'], permission_classes=[IsClassTeacher | IsAdminUser])
    def mark_attendance(self, request, pk=None):
        schedule = self.get_object()
        serializer = ClassAttendanceBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        attendance_date = serializer.validated_data['attendance_date']
        records = serializer.validated_data['records']
        
        created_count = 0
        updated_count = 0
        
        for record in records:
            student_id = record.get('student_id')
            status = record.get('status', 'present')
            notes = record.get('notes')
            
            attendance, created = ClassAttendance.objects.update_or_create(
                schedule=schedule,
                student_id=student_id,
                attendance_date=attendance_date,
                defaults={
                    'status': status,
                    'notes': notes,
                    'marked_by': request.user
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        class_students = ClassStudent.objects.filter(
            class_obj=schedule.class_obj,
            is_active=True
        )
        for cs in class_students:
            attendances = ClassAttendance.objects.filter(
                schedule__class_obj=schedule.class_obj,
                student=cs.student
            )
            total = attendances.count()
            present = attendances.filter(status__in=['present', 'late']).count()
            cs.attendance_rate = present / total if total > 0 else 0
            cs.save()
        
        return Response({
            'message': f'创建 {created_count} 条，更新 {updated_count} 条考勤记录'
        })


class ClassAttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ClassAttendance.objects.select_related(
        'schedule', 'student', 'marked_by'
    )
    serializer_class = ClassAttendanceSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['schedule', 'student', 'status', 'attendance_date']
    ordering_fields = ['attendance_date', 'created_at']
    ordering = ['-attendance_date']

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
            return queryset.filter(schedule__class_obj_id__in=teacher_classes)
        else:
            return queryset.filter(student=user)

    @action(detail=False, methods=['get'])
    def my_attendance(self, request):
        class_obj_id = request.query_params.get('class_id')
        
        queryset = self.get_queryset().filter(student=request.user)
        
        if class_obj_id:
            queryset = queryset.filter(schedule__class_obj_id=class_obj_id)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ClassAttendanceSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ClassAttendanceSerializer(queryset, many=True)
        return Response(serializer.data)


class ClassAnnouncementViewSet(viewsets.ModelViewSet):
    queryset = ClassAnnouncement.objects.select_related(
        'class_obj', 'teacher'
    )
    serializer_class = ClassAnnouncementSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['class_obj', 'priority', 'is_pinned', 'is_draft']
    ordering_fields = ['created_at', 'publish_at']
    ordering = ['-is_pinned', '-created_at']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsClassTeacher | IsAdminUser]
        return [p() for p in permission_classes]

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
            return queryset.filter(
                class_obj_id__in=student_classes,
                is_draft=False
            )

    def perform_create(self, serializer):
        instance = serializer.save(teacher=self.request.user)
        
        if not instance.is_draft and (not instance.publish_at or instance.publish_at <= timezone.now()):
            total_students = instance.class_obj.students.filter(is_active=True).count()
            instance.read_count = 0
            instance.save()


class ClassMaterialViewSet(viewsets.ModelViewSet):
    queryset = ClassMaterial.objects.select_related(
        'class_obj', 'teacher'
    )
    serializer_class = ClassMaterialSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['class_obj', 'category', 'is_free', 'is_locked']
    search_fields = ['title', 'description', 'file_type']
    ordering_fields = ['created_at', 'download_count', 'view_count']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsClassTeacher | IsAdminUser]
        return [p() for p in permission_classes]

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
            return queryset.filter(
                class_obj_id__in=student_classes,
                is_locked=False
            )

    def perform_create(self, serializer):
        file = self.request.FILES.get('file')
        file_type = 'other'
        file_size = 0
        
        if file:
            file_name = file.name.lower()
            if file_name.endswith(('.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx', '.ppt', '.pptx')):
                file_type = 'document'
            elif file_name.endswith(('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')):
                file_type = 'video'
            elif file_name.endswith(('.mp3', '.wav', '.flac', '.aac')):
                file_type = 'audio'
            elif file_name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                file_type = 'image'
            elif file_name.endswith(('.py', '.js', '.ts', '.java', '.cpp', '.c', '.html', '.css', '.json')):
                file_type = 'code'
            
            file_size = file.size
        
        serializer.save(
            teacher=self.request.user,
            file_type=file_type,
            file_size=file_size
        )

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        material = self.get_object()
        
        if material.is_locked and request.user.role not in ['teacher', 'admin'] and not request.user.is_superuser:
            class_student = ClassStudent.objects.filter(
                class_obj=material.class_obj,
                student=request.user,
                is_active=True
            ).first()
            
            if not class_student or not material.is_free:
                return Response(
                    {'error': '无权限下载该资料'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        material.download_count += 1
        material.save()
        
        return Response({
            'message': '开始下载',
            'file_url': material.file.url if material.file else None
        })

    @action(detail=True, methods=['get'])
    def view(self, request, pk=None):
        material = self.get_object()
        material.view_count += 1
        material.save()
        
        return Response(ClassMaterialSerializer(material).data)
