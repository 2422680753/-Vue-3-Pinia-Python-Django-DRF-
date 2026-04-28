from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class UserRole(models.TextChoices):
    STUDENT = 'student', _('学生')
    TEACHER = 'teacher', _('教师')
    ADMIN = 'admin', _('管理员')


class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.STUDENT,
        verbose_name='角色'
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True,
        verbose_name='头像'
    )
    phone = models.CharField(
        max_length=11,
        null=True,
        blank=True,
        verbose_name='手机号'
    )
    real_name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='真实姓名'
    )
    student_id = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        unique=True,
        verbose_name='学号/工号'
    )
    bio = models.TextField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name='个人简介'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_full_name() or self.username} - {self.get_role_display()}'

    @property
    def is_student(self):
        return self.role == UserRole.STUDENT

    @property
    def is_teacher(self):
        return self.role == UserRole.TEACHER

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN


class StudentProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='student_profile',
        verbose_name='用户'
    )
    grade = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name='年级'
    )
    school = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='学校'
    )
    learning_goals = models.TextField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name='学习目标'
    )
    preferred_subjects = models.JSONField(
        default=list,
        verbose_name='偏好科目'
    )

    class Meta:
        verbose_name = '学生档案'
        verbose_name_plural = '学生档案'

    def __str__(self):
        return f'{self.user.username} 的学生档案'


class TeacherProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_profile',
        verbose_name='用户'
    )
    title = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='职称'
    )
    department = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='所属部门'
    )
    expertise = models.TextField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name='专长领域'
    )
    teaching_experience = models.PositiveIntegerField(
        default=0,
        verbose_name='教学经验(年)'
    )
    certifications = models.JSONField(
        default=list,
        verbose_name='资质证书'
    )

    class Meta:
        verbose_name = '教师档案'
        verbose_name_plural = '教师档案'

    def __str__(self):
        return f'{self.user.username} 的教师档案'


class UserLoginRecord(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='login_records',
        verbose_name='用户'
    )
    login_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name='登录时间'
    )
    ip_address = models.GenericIPAddressField(
        verbose_name='IP地址'
    )
    device_info = models.TextField(
        max_length=500,
        verbose_name='设备信息'
    )
    location = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='登录地点'
    )
    is_success = models.BooleanField(
        default=True,
        verbose_name='是否成功'
    )
    failure_reason = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='失败原因'
    )

    class Meta:
        verbose_name = '登录记录'
        verbose_name_plural = '登录记录'
        ordering = ['-login_time']

    def __str__(self):
        return f'{self.user.username} - {self.login_time}'
