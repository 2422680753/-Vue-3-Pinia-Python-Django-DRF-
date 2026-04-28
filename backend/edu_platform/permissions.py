from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or request.user.role == 'admin'
        )


class IsTeacher(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.role == 'teacher' or 
            request.user.is_superuser or 
            request.user.role == 'admin'
        )


class IsStudent(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'student'


class IsCourseInstructor(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'instructor'):
            return obj.instructor == request.user
        if hasattr(obj, 'teacher'):
            return obj.teacher == request.user
        return False


class IsCourseStudent(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        from apps.courses.models import CourseEnrollment
        course = None
        
        if hasattr(obj, 'course'):
            course = obj.course
        elif hasattr(obj, 'chapter'):
            course = obj.chapter.course
        elif hasattr(obj, 'lesson'):
            course = obj.lesson.chapter.course
        
        if course:
            return CourseEnrollment.objects.filter(
                course=course,
                student=request.user,
                is_active=True
            ).exists()
        
        return False


class CanEditCourse(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.role == 'admin':
            return True
        if hasattr(obj, 'instructor'):
            return obj.instructor == request.user
        return False


class IsClassTeacher(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.role == 'admin':
            return True
        if hasattr(obj, 'teacher'):
            return obj.teacher == request.user
        if hasattr(obj, 'class_obj') and obj.class_obj.teacher == request.user:
            return True
        return False


class IsClassStudent(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        from apps.classes.models import ClassStudent
        
        if hasattr(obj, 'student'):
            return obj.student == request.user
        
        class_obj = None
        if hasattr(obj, 'class_obj'):
            class_obj = obj.class_obj
        
        if class_obj:
            return ClassStudent.objects.filter(
                class_obj=class_obj,
                student=request.user,
                is_active=True
            ).exists()
        
        return False


class IsAssignmentOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'student'):
            return obj.student == request.user
        return False


class IsExamAttemptOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'student'):
            return obj.student == request.user
        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'student'):
            return obj.student == request.user
        return False
