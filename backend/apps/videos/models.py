import hashlib
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.conf import settings as django_settings
from django.utils import timezone


class VideoProgress(models.Model):
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.CASCADE,
        related_name='video_progresses',
        verbose_name='课时'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='video_progresses',
        verbose_name='学生'
    )
    
    current_time = models.FloatField(default=0, verbose_name='当前播放时间(秒)')
    total_duration = models.FloatField(default=0, verbose_name='视频总时长(秒)')
    
    play_count = models.PositiveIntegerField(default=0, verbose_name='播放次数')
    watch_duration = models.FloatField(default=0, verbose_name='累计观看时长(秒)')
    
    progress = models.FloatField(default=0, verbose_name='观看进度(0-1)')
    is_completed = models.BooleanField(default=False, verbose_name='是否完成')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    
    last_watched_at = models.DateTimeField(auto_now=True, verbose_name='最后观看时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    version = models.PositiveIntegerField(default=1, verbose_name='版本号')
    last_update_time = models.DateTimeField(auto_now=True, verbose_name='最后更新时间')
    last_update_client = models.CharField(max_length=50, null=True, blank=True, verbose_name='最后更新客户端')
    last_update_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='最后更新IP')

    class Meta:
        verbose_name = '视频进度'
        verbose_name_plural = '视频进度'
        unique_together = ['lesson', 'student']
        ordering = ['-last_watched_at']
        indexes = [
            models.Index(fields=['student', '-last_watched_at']),
            models.Index(fields=['lesson', 'is_completed']),
        ]

    def __str__(self):
        return f'{self.student.username} - {self.lesson.title}'

    def calculate_progress(self):
        if self.total_duration == 0:
            return 0
        return min(self.current_time / self.total_duration, 1.0)

    def check_completion(self):
        threshold = getattr(django_settings, 'VIDEO_COMPLETION_THRESHOLD', 0.9)
        return self.progress >= threshold

    @property
    def course(self):
        return self.lesson.chapter.course
    
    def can_update(self, new_time, new_progress, client_time=None):
        if self.is_completed:
            return False
        
        if new_time < 0:
            return False
        
        if new_time > self.total_duration + 60:
            return False
        
        if new_progress < 0 or new_progress > 1.1:
            return False
        
        if new_time < self.current_time - 300:
            threshold = getattr(django_settings, 'VIDEO_ALLOWED_BACKWARD_SECONDS', 300)
            if self.current_time - new_time > threshold:
                return False
        
        return True
    
    def get_progress_state(self):
        return {
            'current_time': self.current_time,
            'total_duration': self.total_duration,
            'progress': self.progress,
            'is_completed': self.is_completed,
            'version': self.version,
            'last_update_time': self.last_update_time.isoformat() if self.last_update_time else None
        }


class VideoProgressHistory(models.Model):
    video_progress = models.ForeignKey(
        VideoProgress,
        on_delete=models.CASCADE,
        related_name='history_records',
        verbose_name='视频进度'
    )
    
    from_time = models.FloatField(verbose_name='起始时间(秒)')
    to_time = models.FloatField(verbose_name='结束时间(秒)')
    duration = models.FloatField(verbose_name='本次观看时长(秒)')
    
    playback_rate = models.FloatField(default=1.0, verbose_name='播放倍速')
    is_seeked = models.BooleanField(default=False, verbose_name='是否快进/快退')
    seek_from = models.FloatField(null=True, blank=True, verbose_name='快进前时间')
    seek_to = models.FloatField(null=True, blank=True, verbose_name='快进后时间')
    
    session_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='会话ID')
    request_id = models.CharField(max_length=64, null=True, blank=True, verbose_name='请求ID', unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    device_info = models.TextField(max_length=500, null=True, blank=True, verbose_name='设备信息')
    user_agent = models.TextField(null=True, blank=True, verbose_name='User-Agent')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='记录时间')

    class Meta:
        verbose_name = '视频进度历史'
        verbose_name_plural = '视频进度历史'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['video_progress', '-created_at']),
            models.Index(fields=['request_id']),
        ]

    def __str__(self):
        return f'{self.video_progress.student.username} - {self.created_at}'
    
    @staticmethod
    def generate_request_id(*args):
        combined = '_'.join(str(arg) for arg in args)
        return hashlib.md5(combined.encode()).hexdigest()


class VideoProgressConflict(models.Model):
    CONFLICT_TYPES = [
        ('time_backward', '时间回退'),
        ('version_mismatch', '版本不匹配'),
        ('multi_device', '多设备冲突'),
        ('data_inconsistent', '数据不一致'),
    ]
    
    video_progress = models.ForeignKey(
        VideoProgress,
        on_delete=models.CASCADE,
        related_name='conflict_records',
        verbose_name='视频进度'
    )
    
    conflict_type = models.CharField(
        max_length=30,
        choices=CONFLICT_TYPES,
        verbose_name='冲突类型'
    )
    
    server_state = models.JSONField(verbose_name='服务器状态')
    client_state = models.JSONField(verbose_name='客户端状态')
    
    resolution = models.JSONField(null=True, blank=True, verbose_name='解决方案')
    is_resolved = models.BooleanField(default=False, verbose_name='是否已解决')
    
    session_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='会话ID')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    device_info = models.TextField(max_length=500, null=True, blank=True, verbose_name='设备信息')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='解决时间')

    class Meta:
        verbose_name = '视频进度冲突'
        verbose_name_plural = '视频进度冲突'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.video_progress} - {self.get_conflict_type_display()}'


class VideoWatchSession(models.Model):
    video_progress = models.ForeignKey(
        VideoProgress,
        on_delete=models.CASCADE,
        related_name='watch_sessions',
        verbose_name='视频进度'
    )
    
    session_id = models.CharField(max_length=100, unique=True, verbose_name='会话ID')
    start_time = models.DateTimeField(auto_now_add=True, verbose_name='开始时间')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    
    initial_time = models.FloatField(default=0, verbose_name='初始播放位置')
    final_time = models.FloatField(null=True, blank=True, verbose_name='最终播放位置')
    total_seconds = models.FloatField(default=0, verbose_name='本次观看秒数')
    effective_seconds = models.FloatField(default=0, verbose_name='有效观看秒数')
    
    is_active = models.BooleanField(default=True, verbose_name='是否活跃')
    last_heartbeat = models.DateTimeField(auto_now_add=True, verbose_name='最后心跳时间')
    
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    device_info = models.TextField(max_length=500, null=True, blank=True, verbose_name='设备信息')
    user_agent = models.TextField(null=True, blank=True, verbose_name='User-Agent')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '观看会话'
        verbose_name_plural = '观看会话'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['video_progress', '-created_at']),
            models.Index(fields=['session_id']),
            models.Index(fields=['is_active', 'last_heartbeat']),
        ]

    def __str__(self):
        return f'{self.video_progress} - {self.session_id}'
    
    def end_session(self, final_time=None):
        self.is_active = False
        self.end_time = timezone.now()
        if final_time is not None:
            self.final_time = final_time
        self.save()
        
        VideoWatchSession.objects.filter(
            video_progress=self.video_progress,
            is_active=True
        ).exclude(id=self.id).update(
            is_active=False,
            end_time=timezone.now()
        )
    
    def update_heartbeat(self):
        self.last_heartbeat = timezone.now()
        self.save(update_fields=['last_heartbeat'])


class VideoQuality(models.TextChoices):
    AUTO = 'auto', _('自动')
    P240 = '240p', _('240P 流畅')
    P360 = '360p', _('360P 标清')
    P480 = '480p', _('480P 高清')
    P720 = '720p', _('720P 超清')
    P1080 = '1080p', _('1080P 全高清')


class VideoSource(models.Model):
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.CASCADE,
        related_name='video_sources',
        verbose_name='课时'
    )
    
    quality = models.CharField(
        max_length=20,
        choices=VideoQuality.choices,
        default=VideoQuality.AUTO,
        verbose_name='视频质量'
    )
    
    video_url = models.CharField(max_length=500, verbose_name='视频地址')
    file_size = models.BigIntegerField(null=True, blank=True, verbose_name='文件大小(字节)')
    bitrate = models.PositiveIntegerField(null=True, blank=True, verbose_name='码率(kbps)')
    resolution = models.CharField(max_length=20, null=True, blank=True, verbose_name='分辨率')
    
    is_encrypted = models.BooleanField(default=False, verbose_name='是否加密')
    encryption_key = models.CharField(max_length=200, null=True, blank=True, verbose_name='加密密钥')
    drm_provider = models.CharField(
        max_length=20,
        choices=[
            ('none', '无'),
            ('aliyun', '阿里云DRM'),
            ('tencent', '腾讯云DRM'),
            ('custom', '自定义加密'),
        ],
        default='none',
        verbose_name='DRM提供商'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '视频源'
        verbose_name_plural = '视频源'
        ordering = ['quality']
        unique_together = ['lesson', 'quality']

    def __str__(self):
        return f'{self.lesson.title} - {self.get_quality_display()}'


class VideoSubtitle(models.Model):
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.CASCADE,
        related_name='subtitles',
        verbose_name='课时'
    )
    
    language = models.CharField(
        max_length=20,
        choices=[
            ('zh-CN', '简体中文'),
            ('zh-TW', '繁体中文'),
            ('en', '英语'),
            ('ja', '日语'),
            ('ko', '韩语'),
        ],
        default='zh-CN',
        verbose_name='语言'
    )
    
    subtitle_file = models.FileField(upload_to='videos/subtitles/', verbose_name='字幕文件')
    label = models.CharField(max_length=50, null=True, blank=True, verbose_name='显示标签')
    
    is_default = models.BooleanField(default=False, verbose_name='是否默认字幕')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '视频字幕'
        verbose_name_plural = '视频字幕'
        ordering = ['language']

    def __str__(self):
        return f'{self.lesson.title} - {self.get_language_display()}'


class WatchList(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='watch_lists',
        verbose_name='学生'
    )
    
    name = models.CharField(max_length=100, verbose_name='播放列表名称')
    description = models.TextField(max_length=500, null=True, blank=True, verbose_name='描述')
    
    is_public = models.BooleanField(default=False, verbose_name='是否公开')
    is_default = models.BooleanField(default=False, verbose_name='是否默认列表')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '观看列表'
        verbose_name_plural = '观看列表'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student.username} - {self.name}'


class WatchListItem(models.Model):
    watch_list = models.ForeignKey(
        WatchList,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='观看列表'
    )
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.CASCADE,
        related_name='watch_list_items',
        verbose_name='课时'
    )
    
    item_order = models.PositiveIntegerField(default=0, verbose_name='排序')
    added_at = models.DateTimeField(auto_now_add=True, verbose_name='添加时间')

    class Meta:
        verbose_name = '观看列表项'
        verbose_name_plural = '观看列表项'
        ordering = ['item_order']
        unique_together = ['watch_list', 'lesson']

    def __str__(self):
        return f'{self.watch_list.name} - {self.lesson.title}'
