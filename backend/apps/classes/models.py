from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class ClassStatus(models.TextChoices):
    ACTIVE = 'active', _('进行中')
    UPCOMING = 'upcoming', _('即将开始')
    COMPLETED = 'completed', _('已结束')
    ARCHIVED = 'archived', _('已归档')


class Class(models.Model):
    name = models.CharField(max_length=100, verbose_name='班级名称')
    code = models.CharField(max_length=20, unique=True, verbose_name='班级编号')
    description = models.TextField(null=True, blank=True, verbose_name='班级描述')
    
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='classes',
        verbose_name='关联课程'
    )
    
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='taught_classes',
        verbose_name='班主任/主讲教师'
    )
    assistant_teachers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='assisted_classes',
        verbose_name='助教'
    )
    
    max_students = models.PositiveIntegerField(default=50, verbose_name='最大人数')
    current_students = models.PositiveIntegerField(default=0, verbose_name='当前人数')
    
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')
    
    schedule = models.JSONField(
        default=list,
        verbose_name='课程安排',
        help_text='[{'day': 1, 'start_time': '09:00', 'end_time': '11:00'}, ...]'
    )
    
    status = models.CharField(
        max_length=20,
        choices=ClassStatus.choices,
        default=ClassStatus.UPCOMING,
        verbose_name='班级状态'
    )
    
    is_private = models.BooleanField(default=False, verbose_name='是否私密班级')
    join_code = models.CharField(max_length=8, unique=True, null=True, blank=True, verbose_name='加入码')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '班级'
        verbose_name_plural = '班级'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['course', 'status']),
        ]

    def __str__(self):
        return f'{self.name} ({self.code})'


class ClassStudent(models.Model):
    class_obj = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name='students',
        verbose_name='班级'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='class_enrollments',
        verbose_name='学生'
    )
    
    join_type = models.CharField(
        max_length=20,
        choices=[
            ('invite', '教师邀请'),
            ('code', '加入码加入'),
            ('purchase', '购买加入'),
            ('admin', '管理员添加'),
        ],
        default='code',
        verbose_name='加入方式'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='是否在班')
    dropped_at = models.DateTimeField(null=True, blank=True, verbose_name='退班时间')
    drop_reason = models.TextField(null=True, blank=True, verbose_name='退班原因')
    
    final_grade = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='最终成绩'
    )
    attendance_rate = models.FloatField(default=0, verbose_name='出勤率(0-1)')
    is_graduated = models.BooleanField(default=False, verbose_name='是否结业')
    graduated_at = models.DateTimeField(null=True, blank=True, verbose_name='结业时间')
    
    notes = models.TextField(null=True, blank=True, verbose_name='教师备注')
    
    enrolled_at = models.DateTimeField(auto_now_add=True, verbose_name='入班时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '班级学生'
        verbose_name_plural = '班级学生'
        unique_together = ['class_obj', 'student']
        ordering = ['enrolled_at']

    def __str__(self):
        return f'{self.class_obj.name} - {self.student.username}'


class ClassSchedule(models.Model):
    class_obj = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name='schedules',
        verbose_name='班级'
    )
    
    title = models.CharField(max_length=100, verbose_name='课程标题')
    description = models.TextField(null=True, blank=True, verbose_name='课程描述')
    
    day_of_week = models.PositiveSmallIntegerField(
        choices=[
            (0, '周一'),
            (1, '周二'),
            (2, '周三'),
            (3, '周四'),
            (4, '周五'),
            (5, '周六'),
            (6, '周日'),
        ],
        verbose_name='星期'
    )
    start_time = models.TimeField(verbose_name='开始时间')
    end_time = models.TimeField(verbose_name='结束时间')
    
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')
    
    is_recurring = models.BooleanField(default=True, verbose_name='是否重复')
    repeat_weeks = models.PositiveIntegerField(default=1, verbose_name='重复周数')
    
    location = models.CharField(max_length=100, null=True, blank=True, verbose_name='上课地点')
    meeting_url = models.URLField(null=True, blank=True, verbose_name='在线会议链接')
    
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_schedules',
        verbose_name='授课教师'
    )
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_schedules',
        verbose_name='关联课时'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '班级课程安排'
        verbose_name_plural = '班级课程安排'
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f'{self.class_obj.name} - {self.title}'


class ClassAttendance(models.Model):
    schedule = models.ForeignKey(
        ClassSchedule,
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name='课程安排'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='class_attendances',
        verbose_name='学生'
    )
    
    attendance_date = models.DateField(verbose_name='考勤日期')
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('present', '出勤'),
            ('late', '迟到'),
            ('early_leave', '早退'),
            ('absent', '缺勤'),
            ('excused', '请假'),
        ],
        default='present',
        verbose_name='考勤状态'
    )
    
    check_in_time = models.DateTimeField(null=True, blank=True, verbose_name='签到时间')
    check_out_time = models.DateTimeField(null=True, blank=True, verbose_name='签退时间')
    
    notes = models.TextField(null=True, blank=True, verbose_name='备注')
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marked_attendances',
        verbose_name='标记人'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '考勤记录'
        verbose_name_plural = '考勤记录'
        unique_together = ['schedule', 'student', 'attendance_date']
        ordering = ['-attendance_date']

    def __str__(self):
        return f'{self.student.username} - {self.attendance_date}'


class ClassAnnouncement(models.Model):
    class_obj = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name='announcements',
        verbose_name='班级'
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='class_announcements',
        verbose_name='发布人'
    )
    
    title = models.CharField(max_length=200, verbose_name='公告标题')
    content = models.TextField(verbose_name='公告内容')
    
    priority = models.CharField(
        max_length=20,
        choices=[
            ('low', '普通'),
            ('medium', '重要'),
            ('high', '紧急'),
        ],
        default='medium',
        verbose_name='优先级'
    )
    
    is_pinned = models.BooleanField(default=False, verbose_name='是否置顶')
    attachments = models.FileField(
        upload_to='classes/announcements/',
        null=True,
        blank=True,
        verbose_name='附件'
    )
    
    publish_at = models.DateTimeField(null=True, blank=True, verbose_name='定时发布时间')
    expire_at = models.DateTimeField(null=True, blank=True, verbose_name='过期时间')
    
    read_count = models.PositiveIntegerField(default=0, verbose_name='已读人数')
    
    is_draft = models.BooleanField(default=False, verbose_name='是否草稿')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '班级公告'
        verbose_name_plural = '班级公告'
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f'{self.class_obj.name} - {self.title}'


class ClassMaterial(models.Model):
    class_obj = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name='materials',
        verbose_name='班级'
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='class_materials',
        verbose_name='上传人'
    )
    
    title = models.CharField(max_length=200, verbose_name='资料标题')
    description = models.TextField(null=True, blank=True, verbose_name='资料描述')
    
    file = models.FileField(upload_to='classes/materials/', verbose_name='文件')
    file_type = models.CharField(max_length=50, verbose_name='文件类型')
    file_size = models.BigIntegerField(verbose_name='文件大小(字节)')
    
    download_count = models.PositiveIntegerField(default=0, verbose_name='下载次数')
    view_count = models.PositiveIntegerField(default=0, verbose_name='查看次数')
    
    is_free = models.BooleanField(default=True, verbose_name='是否免费')
    is_locked = models.BooleanField(default=False, verbose_name='是否锁定')
    
    category = models.CharField(
        max_length=20,
        choices=[
            ('document', '文档资料'),
            ('video', '视频资料'),
            ('audio', '音频资料'),
            ('image', '图片资料'),
            ('code', '代码资料'),
            ('other', '其他'),
        ],
        default='document',
        verbose_name='资料分类'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '班级资料'
        verbose_name_plural = '班级资料'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.class_obj.name} - {self.title}'
