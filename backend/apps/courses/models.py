from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db.models import Avg, Count


class CourseStatus(models.TextChoices):
    DRAFT = 'draft', _('草稿')
    PUBLISHED = 'published', _('已发布')
    ARCHIVED = 'archived', _('已归档')


class CourseType(models.TextChoices):
    LIVE = 'live', _('直播课')
    RECORDED = 'recorded', _('录播课')
    HYBRID = 'hybrid', _('混合课程')


class CourseLevel(models.TextChoices):
    BEGINNER = 'beginner', _('入门级')
    INTERMEDIATE = 'intermediate', _('进阶级')
    ADVANCED = 'advanced', _('高级')


class Category(models.Model):
    name = models.CharField(max_length=50, verbose_name='分类名称')
    slug = models.SlugField(unique=True, verbose_name='分类标识')
    description = models.TextField(max_length=200, null=True, blank=True, verbose_name='描述')
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='父分类'
    )
    icon = models.ImageField(upload_to='categories/', null=True, blank=True, verbose_name='分类图标')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '课程分类'
        verbose_name_plural = '课程分类'
        ordering = ['sort_order', '-created_at']

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=30, unique=True, verbose_name='标签名称')
    color = models.CharField(max_length=7, default='#007bff', verbose_name='标签颜色')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '课程标签'
        verbose_name_plural = '课程标签'

    def __str__(self):
        return self.name


class Course(models.Model):
    title = models.CharField(max_length=200, verbose_name='课程标题')
    slug = models.SlugField(unique=True, verbose_name='课程标识')
    description = models.TextField(verbose_name='课程描述')
    short_description = models.CharField(max_length=200, verbose_name='简短描述')
    
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='taught_courses',
        verbose_name='授课教师'
    )
    
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
        verbose_name='课程分类'
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='courses', verbose_name='课程标签')
    
    course_type = models.CharField(
        max_length=20,
        choices=CourseType.choices,
        default=CourseType.RECORDED,
        verbose_name='课程类型'
    )
    level = models.CharField(
        max_length=20,
        choices=CourseLevel.choices,
        default=CourseLevel.BEGINNER,
        verbose_name='难度等级'
    )
    
    cover_image = models.ImageField(upload_to='courses/covers/', verbose_name='封面图片')
    preview_video = models.FileField(upload_to='courses/previews/', null=True, blank=True, verbose_name='预览视频')
    
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='价格')
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='原价')
    
    duration = models.PositiveIntegerField(default=0, verbose_name='总时长(分钟)')
    total_lessons = models.PositiveIntegerField(default=0, verbose_name='总课时')
    total_students = models.PositiveIntegerField(default=0, verbose_name='学习人数')
    
    status = models.CharField(
        max_length=20,
        choices=CourseStatus.choices,
        default=CourseStatus.DRAFT,
        verbose_name='课程状态'
    )
    
    is_featured = models.BooleanField(default=False, verbose_name='是否推荐')
    is_free = models.BooleanField(default=False, verbose_name='是否免费')
    
    requirements = models.TextField(null=True, blank=True, verbose_name='学习要求')
    target_audience = models.TextField(null=True, blank=True, verbose_name='适合人群')
    objectives = models.TextField(null=True, blank=True, verbose_name='学习目标')
    
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '课程'
        verbose_name_plural = '课程'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['category', 'level']),
        ]

    def __str__(self):
        return self.title

    @property
    def average_rating(self):
        return self.reviews.aggregate(Avg('rating'))['rating__avg'] or 0

    @property
    def review_count(self):
        return self.reviews.count()

    def get_discount_percent(self):
        if self.original_price and self.price < self.original_price:
            return int((1 - self.price / self.original_price) * 100)
        return 0


class Chapter(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='chapters',
        verbose_name='所属课程'
    )
    title = models.CharField(max_length=100, verbose_name='章节标题')
    description = models.TextField(null=True, blank=True, verbose_name='章节描述')
    chapter_order = models.PositiveIntegerField(default=0, verbose_name='章节顺序')
    duration = models.PositiveIntegerField(default=0, verbose_name='章节时长(分钟)')
    is_locked = models.BooleanField(default=False, verbose_name='是否锁定')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '课程章节'
        verbose_name_plural = '课程章节'
        ordering = ['chapter_order']
        unique_together = ['course', 'chapter_order']

    def __str__(self):
        return f'{self.course.title} - {self.title}'


class Lesson(models.Model):
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name='所属章节'
    )
    title = models.CharField(max_length=100, verbose_name='课时标题')
    description = models.TextField(null=True, blank=True, verbose_name='课时描述')
    lesson_order = models.PositiveIntegerField(default=0, verbose_name='课时顺序')
    duration = models.PositiveIntegerField(default=0, verbose_name='时长(分钟)')
    
    video_url = models.FileField(upload_to='lessons/videos/', null=True, blank=True, verbose_name='视频文件')
    external_video_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='外部视频ID')
    video_provider = models.CharField(
        max_length=20,
        choices=[
            ('local', '本地存储'),
            ('aliyun', '阿里云OSS'),
            ('qiniu', '七牛云'),
            ('tencent', '腾讯云'),
        ],
        default='local',
        verbose_name='视频存储提供商'
    )
    
    is_free = models.BooleanField(default=False, verbose_name='是否免费观看')
    is_locked = models.BooleanField(default=False, verbose_name='是否锁定')
    requires_completion = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dependent_lessons',
        verbose_name='需要先完成的课时'
    )
    
    attachments = models.FileField(upload_to='lessons/attachments/', null=True, blank=True, verbose_name='附件资料')
    notes = models.TextField(null=True, blank=True, verbose_name='教师备注')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '课时'
        verbose_name_plural = '课时'
        ordering = ['lesson_order']
        unique_together = ['chapter', 'lesson_order']

    def __str__(self):
        return f'{self.chapter.title} - {self.title}'

    @property
    def course(self):
        return self.chapter.course


class CourseEnrollment(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='课程'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='学生'
    )
    
    enrollment_type = models.CharField(
        max_length=20,
        choices=[
            ('purchase', '购买'),
            ('free', '免费加入'),
            ('invite', '教师邀请'),
            ('class', '班级加入'),
        ],
        default='free',
        verbose_name='加入方式'
    )
    
    price_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='支付金额')
    progress = models.FloatField(default=0, verbose_name='学习进度(0-1)')
    
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    is_completed = models.BooleanField(default=False, verbose_name='是否完成')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    
    last_accessed_at = models.DateTimeField(auto_now=True, verbose_name='最后访问时间')
    enrolled_at = models.DateTimeField(auto_now_add=True, verbose_name='加入时间')

    class Meta:
        verbose_name = '课程报名'
        verbose_name_plural = '课程报名'
        unique_together = ['course', 'student']
        ordering = ['-enrolled_at']
        indexes = [
            models.Index(fields=['student', '-last_accessed_at']),
        ]

    def __str__(self):
        return f'{self.student.username} - {self.course.title}'

    def calculate_progress(self):
        from apps.videos.models import VideoProgress
        total_lessons = self.course.lessons.count()
        if total_lessons == 0:
            return 0
        
        completed_lessons = VideoProgress.objects.filter(
            lesson__chapter__course=self.course,
            student=self.student,
            is_completed=True
        ).count()
        
        return completed_lessons / total_lessons


class CourseReview(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='课程'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_reviews',
        verbose_name='学生'
    )
    
    rating = models.PositiveSmallIntegerField(
        choices=[(i, f'{i}星') for i in range(1, 6)],
        verbose_name='评分'
    )
    content = models.TextField(max_length=1000, verbose_name='评价内容')
    
    is_anonymous = models.BooleanField(default=False, verbose_name='是否匿名')
    is_featured = models.BooleanField(default=False, verbose_name='是否精选')
    
    likes_count = models.PositiveIntegerField(default=0, verbose_name='点赞数')
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name='回复评论'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '课程评价'
        verbose_name_plural = '课程评价'
        unique_together = ['course', 'student']
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student.username} - {self.course.title} ({self.rating}星)'


class LiveCourse(models.Model):
    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        related_name='live_info',
        verbose_name='课程'
    )
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='live_courses',
        verbose_name='主播教师'
    )
    
    start_time = models.DateTimeField(verbose_name='开始时间')
    end_time = models.DateTimeField(verbose_name='结束时间')
    stream_url = models.URLField(null=True, blank=True, verbose_name='直播流地址')
    playback_url = models.URLField(null=True, blank=True, verbose_name='回放地址')
    
    max_viewers = models.PositiveIntegerField(default=1000, verbose_name='最大观看人数')
    current_viewers = models.PositiveIntegerField(default=0, verbose_name='当前观看人数')
    total_viewers = models.PositiveIntegerField(default=0, verbose_name='累计观看人数')
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('scheduled', '未开始'),
            ('live', '直播中'),
            ('ended', '已结束'),
            ('canceled', '已取消'),
        ],
        default='scheduled',
        verbose_name='直播状态'
    )
    
    is_interactive = models.BooleanField(default=True, verbose_name='是否允许互动')
    has_recording = models.BooleanField(default=True, verbose_name='是否录制')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '直播课程'
        verbose_name_plural = '直播课程'
        ordering = ['-start_time']

    def __str__(self):
        return f'直播: {self.course.title}'


class LiveChatMessage(models.Model):
    live_course = models.ForeignKey(
        LiveCourse,
        on_delete=models.CASCADE,
        related_name='chat_messages',
        verbose_name='直播课程'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='live_chat_messages',
        verbose_name='用户'
    )
    content = models.TextField(max_length=500, verbose_name='消息内容')
    message_type = models.CharField(
        max_length=20,
        choices=[
            ('chat', '聊天'),
            ('question', '提问'),
            ('system', '系统消息'),
        ],
        default='chat',
        verbose_name='消息类型'
    )
    is_answered = models.BooleanField(default=False, verbose_name='是否已解答')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='发送时间')

    class Meta:
        verbose_name = '直播聊天消息'
        verbose_name_plural = '直播聊天消息'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.user.username}: {self.content[:20]}'
