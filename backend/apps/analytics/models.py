from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class LearningSession(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='learning_sessions',
        verbose_name='学生'
    )
    
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='learning_sessions',
        verbose_name='课程'
    )
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='learning_sessions',
        verbose_name='课时'
    )
    
    session_type = models.CharField(
        max_length=20,
        choices=[
            ('video', '视频学习'),
            ('reading', '阅读学习'),
            ('assignment', '作业学习'),
            ('exam', '考试学习'),
            ('live', '直播学习'),
            ('other', '其他学习'),
        ],
        default='video',
        verbose_name='学习类型'
    )
    
    start_time = models.DateTimeField(verbose_name='开始时间')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    
    duration = models.PositiveIntegerField(null=True, blank=True, verbose_name='持续时间(秒)')
    effective_duration = models.PositiveIntegerField(default=0, verbose_name='有效学习时间(秒)')
    
    is_active = models.BooleanField(default=True, verbose_name='是否进行中')
    
    device_info = models.TextField(max_length=500, null=True, blank=True, verbose_name='设备信息')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    location = models.CharField(max_length=100, null=True, blank=True, verbose_name='地理位置')
    
    interactions = models.JSONField(default=list, verbose_name='交互记录')
    focus_intervals = models.JSONField(default=list, verbose_name='专注区间')
    distraction_events = models.JSONField(default=list, verbose_name='分心事件')
    
    focus_score = models.FloatField(null=True, blank=True, verbose_name='专注度评分(0-1)')
    efficiency_score = models.FloatField(null=True, blank=True, verbose_name='学习效率评分(0-1)')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '学习会话'
        verbose_name_plural = '学习会话'
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['student', '-start_time']),
            models.Index(fields=['course', '-start_time']),
        ]

    def __str__(self):
        return f'{self.student.username} - {self.course.title} ({self.start_time})'


class DailyLearningStats(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daily_stats',
        verbose_name='学生'
    )
    
    date = models.DateField(verbose_name='日期')
    
    total_sessions = models.PositiveIntegerField(default=0, verbose_name='学习次数')
    total_duration = models.PositiveIntegerField(default=0, verbose_name='总学习时长(秒)')
    effective_duration = models.PositiveIntegerField(default=0, verbose_name='有效学习时长(秒)')
    
    courses_visited = models.PositiveIntegerField(default=0, verbose_name='访问课程数')
    lessons_completed = models.PositiveIntegerField(default=0, verbose_name='完成课时数')
    
    assignments_submitted = models.PositiveIntegerField(default=0, verbose_name='提交作业数')
    assignments_graded = models.PositiveIntegerField(default=0, verbose_name='已批改作业数')
    
    exams_taken = models.PositiveIntegerField(default=0, verbose_name='参加考试数')
    exams_passed = models.PositiveIntegerField(default=0, verbose_name='通过考试数')
    
    average_focus_score = models.FloatField(null=True, blank=True, verbose_name='平均专注度')
    average_efficiency_score = models.FloatField(null=True, blank=True, verbose_name='平均效率')
    
    streak_days = models.PositiveIntegerField(default=0, verbose_name='连续学习天数')
    is_learning_day = models.BooleanField(default=True, verbose_name='是否为学习日')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '日学习统计'
        verbose_name_plural = '日学习统计'
        unique_together = ['student', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['student', '-date']),
        ]

    def __str__(self):
        return f'{self.student.username} - {self.date}'


class CourseProgressStats(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_progress_stats',
        verbose_name='学生'
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='progress_stats',
        verbose_name='课程'
    )
    
    enrollment = models.OneToOneField(
        'courses.CourseEnrollment',
        on_delete=models.CASCADE,
        related_name='progress_stats',
        verbose_name='报名记录'
    )
    
    overall_progress = models.FloatField(default=0, verbose_name='整体进度(0-1)')
    
    total_lessons = models.PositiveIntegerField(default=0, verbose_name='总课时数')
    completed_lessons = models.PositiveIntegerField(default=0, verbose_name='已完成课时数')
    in_progress_lessons = models.PositiveIntegerField(default=0, verbose_name='进行中课时数')
    
    total_video_duration = models.PositiveIntegerField(default=0, verbose_name='总视频时长(秒)')
    watched_video_duration = models.PositiveIntegerField(default=0, verbose_name='已观看时长(秒)')
    
    total_assignments = models.PositiveIntegerField(default=0, verbose_name='作业总数')
    submitted_assignments = models.PositiveIntegerField(default=0, verbose_name='已提交作业数')
    graded_assignments = models.PositiveIntegerField(default=0, verbose_name='已批改作业数')
    
    assignments_average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='作业平均分'
    )
    
    total_exams = models.PositiveIntegerField(default=0, verbose_name='考试总数')
    taken_exams = models.PositiveIntegerField(default=0, verbose_name='已参加考试数')
    passed_exams = models.PositiveIntegerField(default=0, verbose_name='通过考试数')
    
    exams_average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='考试平均分'
    )
    
    first_access_at = models.DateTimeField(null=True, blank=True, verbose_name='首次访问时间')
    last_access_at = models.DateTimeField(null=True, blank=True, verbose_name='最后访问时间')
    
    total_study_time = models.PositiveIntegerField(default=0, verbose_name='总学习时间(秒)')
    estimated_remaining_time = models.PositiveIntegerField(default=0, verbose_name='预计剩余时间(秒)')
    
    learning_speed_score = models.FloatField(null=True, blank=True, verbose_name='学习速度评分')
    mastery_score = models.FloatField(null=True, blank=True, verbose_name='掌握程度评分')
    
    predicted_completion_date = models.DateField(null=True, blank=True, verbose_name='预计完成日期')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '课程进度统计'
        verbose_name_plural = '课程进度统计'
        unique_together = ['student', 'course']
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.student.username} - {self.course.title}'


class LearningBehavior(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='learning_behaviors',
        verbose_name='学生'
    )
    
    behavior_type = models.CharField(
        max_length=50,
        choices=[
            ('video_play', '播放视频'),
            ('video_pause', '暂停视频'),
            ('video_seek', '快进/快退'),
            ('video_speed_change', '改变播放速度'),
            ('lesson_start', '开始学习课时'),
            ('lesson_complete', '完成课时'),
            ('chapter_start', '开始章节'),
            ('chapter_complete', '完成章节'),
            ('assignment_start', '开始作业'),
            ('assignment_submit', '提交作业'),
            ('exam_start', '开始考试'),
            ('exam_submit', '提交考试'),
            ('material_download', '下载资料'),
            ('material_view', '查看资料'),
            ('note_create', '创建笔记'),
            ('note_update', '更新笔记'),
            ('question_ask', '提问'),
            ('question_answer', '回答问题'),
            ('discussion_post', '发帖讨论'),
            ('tab_switch', '切换页面'),
            ('idle_start', '开始空闲'),
            ('idle_end', '结束空闲'),
        ],
        verbose_name='行为类型'
    )
    
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='learning_behaviors',
        verbose_name='课程'
    )
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='learning_behaviors',
        verbose_name='课时'
    )
    
    details = models.JSONField(default=dict, verbose_name='行为详情')
    
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='时间戳')
    session_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='会话ID')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '学习行为'
        verbose_name_plural = '学习行为'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['student', '-timestamp']),
            models.Index(fields=['course', '-timestamp']),
        ]

    def __str__(self):
        return f'{self.student.username} - {self.get_behavior_type_display()}'


class LearningAnalytics(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='analytics_records',
        verbose_name='学生'
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='analytics_records',
        verbose_name='课程'
    )
    
    analysis_date = models.DateField(verbose_name='分析日期')
    
    overall_engagement_score = models.FloatField(null=True, blank=True, verbose_name='整体参与度评分')
    
    video_watching_pattern = models.JSONField(default=dict, verbose_name='视频观看模式')
    video_completion_rate = models.FloatField(null=True, blank=True, verbose_name='视频完成率')
    average_playback_speed = models.FloatField(null=True, blank=True, verbose_name='平均播放速度')
    seek_frequency = models.FloatField(null=True, blank=True, verbose_name='快进频率')
    
    assignment_submission_pattern = models.JSONField(default=dict, verbose_name='作业提交模式')
    assignment_on_time_rate = models.FloatField(null=True, blank=True, verbose_name='作业按时提交率')
    assignment_avg_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='作业平均分'
    )
    
    exam_performance = models.JSONField(default=dict, verbose_name='考试表现')
    exam_avg_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='考试平均分'
    )
    exam_pass_rate = models.FloatField(null=True, blank=True, verbose_name='考试通过率')
    
    learning_time_distribution = models.JSONField(default=dict, verbose_name='学习时间分布')
    peak_learning_hours = models.JSONField(default=list, verbose_name='高峰学习时段')
    weekly_learning_pattern = models.JSONField(default=dict, verbose_name='周学习模式')
    
    focus_analysis = models.JSONField(default=dict, verbose_name='专注度分析')
    average_focus_score = models.FloatField(null=True, blank=True, verbose_name='平均专注度')
    distraction_events_count = models.PositiveIntegerField(default=0, verbose_name='分心事件数')
    
    predictions = models.JSONField(default=dict, verbose_name='预测分析')
    predicted_final_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='预测最终成绩'
    )
    completion_probability = models.FloatField(null=True, blank=True, verbose_name='完成概率')
    dropout_risk = models.CharField(
        max_length=20,
        choices=[
            ('low', '低风险'),
            ('medium', '中等风险'),
            ('high', '高风险'),
        ],
        null=True,
        blank=True,
        verbose_name='辍学风险'
    )
    
    strengths = models.JSONField(default=list, verbose_name='学习优势')
    weaknesses = models.JSONField(default=list, verbose_name='学习薄弱点')
    recommendations = models.JSONField(default=list, verbose_name='学习建议')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '学习分析'
        verbose_name_plural = '学习分析'
        unique_together = ['student', 'course', 'analysis_date']
        ordering = ['-analysis_date']

    def __str__(self):
        return f'{self.student.username} - {self.course.title} ({self.analysis_date})'


class ClassAnalytics(models.Model):
    class_obj = models.ForeignKey(
        'classes.Class',
        on_delete=models.CASCADE,
        related_name='analytics',
        verbose_name='班级'
    )
    
    analysis_date = models.DateField(verbose_name='分析日期')
    
    total_students = models.PositiveIntegerField(default=0, verbose_name='总学生数')
    active_students = models.PositiveIntegerField(default=0, verbose_name='活跃学生数')
    at_risk_students = models.PositiveIntegerField(default=0, verbose_name='风险学生数')
    
    average_attendance_rate = models.FloatField(null=True, blank=True, verbose_name='平均出勤率')
    average_progress = models.FloatField(null=True, blank=True, verbose_name='平均进度')
    
    assignment_submission_rate = models.FloatField(null=True, blank=True, verbose_name='作业提交率')
    assignment_average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='作业平均分'
    )
    
    exam_average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='考试平均分'
    )
    exam_pass_rate = models.FloatField(null=True, blank=True, verbose_name='考试通过率')
    
    weekly_activity_trend = models.JSONField(default=list, verbose_name='周活动趋势')
    score_distribution = models.JSONField(default=dict, verbose_name='成绩分布')
    progress_distribution = models.JSONField(default=dict, verbose_name='进度分布')
    
    top_performers = models.JSONField(default=list, verbose_name='优秀学生')
    struggling_students = models.JSONField(default=list, verbose_name='困难学生')
    
    class_engagement_score = models.FloatField(null=True, blank=True, verbose_name='班级参与度评分')
    learning_efficiency_index = models.FloatField(null=True, blank=True, verbose_name='学习效率指数')
    
    insights = models.JSONField(default=list, verbose_name='班级洞察')
    recommendations = models.JSONField(default=list, verbose_name='教学建议')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '班级分析'
        verbose_name_plural = '班级分析'
        unique_together = ['class_obj', 'analysis_date']
        ordering = ['-analysis_date']

    def __str__(self):
        return f'{self.class_obj.name} - {self.analysis_date}'
