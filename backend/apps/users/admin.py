from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, StudentProfile, TeacherProfile, UserLoginRecord


class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    verbose_name_plural = '学生档案'


class TeacherProfileInline(admin.StackedInline):
    model = TeacherProfile
    can_delete = False
    verbose_name_plural = '教师档案'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [StudentProfileInline, TeacherProfileInline]
    list_display = [
        'username', 'email', 'real_name', 'role', 'phone',
        'is_active', 'is_staff', 'created_at'
    ]
    list_filter = ['role', 'is_active', 'is_staff', 'created_at']
    search_fields = ['username', 'email', 'real_name', 'phone']
    readonly_fields = ['last_login', 'date_joined', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {'fields': (
            'email', 'phone', 'real_name', 'student_id', 'avatar',
            'role', 'bio'
        )}),
        ('权限', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('重要日期', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role'),
        }),
    )
    
    ordering = ['-created_at']


@admin.register(UserLoginRecord)
class UserLoginRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'login_time', 'ip_address', 'device_info', 'is_success']
    list_filter = ['is_success', 'login_time']
    search_fields = ['user__username', 'ip_address']
    readonly_fields = ['user', 'login_time', 'ip_address', 'device_info', 'location', 'is_success', 'failure_reason']
    
    def has_add_permission(self, request):
        return False
