from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.conf import settings as django_settings


class ExamType(models.TextChoices):
    QUIZ = 'quiz', _('随堂测验')
    MIDTERM = 'midterm', _('期中考试')
    FINAL = 'final', _('期末考试')
    PRACTICE = 'practice', _('模拟练习')
    CERTIFICATION = 'certification', _('认证考试')


class ExamStatus(models.TextChoices):
    DRAFT = 'draft', _('草稿')
    PUBLISHED = 'published', _('已发布')
    ACTIVE = 'active', _('进行中')
    ENDED = 'ended', _('已结束')
    ARCHIVED = 'archived', _('已归档')


class QuestionType(models.TextChoices):
    SINGLE_CHOICE = 'single_choice', _('单选题')
    MULTI_CHOICE = 'multi_choice', _('多选题')
    TRUE_FALSE = 'true_false', _('判断题')
    FILL_BLANK = 'fill_blank', _('填空题')
    SHORT_ANSWER = 'short_answer', _('简答题')
    ESSAY = 'essay', _('论述题')


class ExamDifficulty(models.TextChoices):
    EASY = 'easy', _('简单')
    MEDIUM = 'medium', _('中等')
    HARD = 'hard', _('困难')


class Exam(models.Model):
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='exams',
        verbose_name='所属课程'
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_exams',
        verbose_name='出卷教师'
    )
    
    title = models.CharField(max_length=200, verbose_name='考试标题')
    description = models.TextField(verbose_name='考试描述')
    exam_type = models.CharField(
        max_length=20,
        choices=ExamType.choices,
        default=ExamType.MIDTERM,
        verbose_name='考试类型'
    )
    
    total_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.00, verbose_name='总分')
    pass_score = models.DecimalField(max_digits=5, decimal_places=2, default=60.00, verbose_name='及格分数')
    total_questions = models.PositiveIntegerField(default=0, verbose_name='题目总数')
    
    duration = models.PositiveIntegerField(verbose_name='考试时长(分钟)')
    allow_enter_before = models.PositiveIntegerField(default=5, verbose_name='允许提前进入(分钟)')
    
    start_time = models.DateTimeField(verbose_name='开始时间')
    end_time = models.DateTimeField(verbose_name='结束时间')
    
    allow_late_enter = models.BooleanField(default=False, verbose_name='允许迟到进入')
    late_enter_limit = models.PositiveIntegerField(default=0, verbose_name='迟到限制(分钟)')
    
    status = models.CharField(
        max_length=20,
        choices=ExamStatus.choices,
        default=ExamStatus.DRAFT,
        verbose_name='考试状态'
    )
    
    show_score_immediately = models.BooleanField(default=False, verbose_name='立即显示成绩')
    show_answers_after_exam = models.BooleanField(default=True, verbose_name='考后显示答案')
    show_analysis = models.BooleanField(default=True, verbose_name='显示解析')
    
    max_attempts = models.PositiveIntegerField(default=1, verbose_name='允许考试次数')
    auto_submit_on_timeout = models.BooleanField(default=True, verbose_name='超时自动提交')
    
    is_shuffle_questions = models.BooleanField(default=False, verbose_name='随机题目顺序')
    is_shuffle_options = models.BooleanField(default=False, verbose_name='随机选项顺序')
    is_question_pool = models.BooleanField(default=False, verbose_name='随机抽题')
    questions_per_student = models.PositiveIntegerField(default=0, verbose_name='每人题目数')
    
    enable_anti_cheating = models.BooleanField(default=True, verbose_name='启用防作弊')
    max_tab_switches = models.PositiveIntegerField(default=3, verbose_name='最大切屏次数')
    max_idle_time = models.PositiveIntegerField(default=300, verbose_name='最大空闲时间(秒)')
    require_fullscreen = models.BooleanField(default=True, verbose_name='要求全屏')
    block_copy_paste = models.BooleanField(default=True, verbose_name='阻止复制粘贴')
    block_right_click = models.BooleanField(default=True, verbose_name='阻止右键')
    enable_face_verification = models.BooleanField(default=False, verbose_name='启用人脸验证')
    verify_interval = models.PositiveIntegerField(default=600, verbose_name='验证间隔(秒)')
    
    password = models.CharField(max_length=50, null=True, blank=True, verbose_name='考试密码')
    ip_whitelist = models.JSONField(default=list, null=True, blank=True, verbose_name='IP白名单')
    
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '考试'
        verbose_name_plural = '考试'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['course', 'status']),
            models.Index(fields=['start_time', 'end_time']),
        ]

    def __str__(self):
        return f'{self.course.title} - {self.title}'

    def get_max_tab_switches(self):
        return self.max_tab_switches or getattr(django_settings, 'EXAM_MAX_TAB_SWITCHES', 3)

    def get_max_idle_time(self):
        return self.max_idle_time or getattr(django_settings, 'EXAM_MAX_IDLE_TIME', 300)


class QuestionBank(models.Model):
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='question_banks',
        verbose_name='所属课程'
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='question_banks',
        verbose_name='创建教师'
    )
    
    chapter = models.ForeignKey(
        'courses.Chapter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='question_banks',
        verbose_name='所属章节'
    )
    
    question_text = models.TextField(verbose_name='题目内容')
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE_CHOICE,
        verbose_name='题目类型'
    )
    
    difficulty = models.CharField(
        max_length=10,
        choices=ExamDifficulty.choices,
        default=ExamDifficulty.MEDIUM,
        verbose_name='难度'
    )
    
    options = models.JSONField(
        default=list,
        null=True,
        blank=True,
        verbose_name='选项',
        help_text='[{"value": "A", "text": "选项A"}, ...]'
    )
    correct_answer = models.JSONField(
        default=dict,
        verbose_name='正确答案',
        help_text='单选: {"answer": "A"}, 多选: {"answers": ["A","B"]}, 填空: {"answers": ["答案1","答案2"]}'
    )
    
    score = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, verbose_name='默认分值')
    explanation = models.TextField(null=True, blank=True, verbose_name='答案解析')
    
    tags = models.ManyToManyField(
        'courses.Tag',
        blank=True,
        related_name='questions',
        verbose_name='标签'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    usage_count = models.PositiveIntegerField(default=0, verbose_name='使用次数')
    correct_rate = models.FloatField(default=0, verbose_name='正确率(0-1)')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '题库'
        verbose_name_plural = '题库'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['course', 'question_type', 'difficulty']),
        ]

    def __str__(self):
        return f'{self.get_question_type_display()} - {self.question_text[:50]}'


class ExamQuestion(models.Model):
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='exam_questions',
        verbose_name='考试'
    )
    question_bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exam_questions',
        verbose_name='题库题目'
    )
    
    question_text = models.TextField(verbose_name='题目内容')
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE_CHOICE,
        verbose_name='题目类型'
    )
    
    options = models.JSONField(
        default=list,
        null=True,
        blank=True,
        verbose_name='选项'
    )
    correct_answer = models.JSONField(
        default=dict,
        verbose_name='正确答案'
    )
    
    question_order = models.PositiveIntegerField(verbose_name='题目顺序')
    score = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, verbose_name='分值')
    explanation = models.TextField(null=True, blank=True, verbose_name='答案解析')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '考试题目'
        verbose_name_plural = '考试题目'
        ordering = ['question_order']
        unique_together = ['exam', 'question_order']

    def __str__(self):
        return f'Q{self.question_order}: {self.question_text[:50]}'


class ExamAttempt(models.Model):
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name='考试'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exam_attempts',
        verbose_name='学生'
    )
    
    attempt_number = models.PositiveIntegerField(verbose_name='考试次数')
    
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    submit_time = models.DateTimeField(null=True, blank=True, verbose_name='提交时间')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    
    time_spent = models.PositiveIntegerField(null=True, blank=True, verbose_name='用时(秒)')
    
    total_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='总得分'
    )
    score_percentage = models.FloatField(null=True, blank=True, verbose_name='得分率(0-1)')
    is_passed = models.BooleanField(null=True, blank=True, verbose_name='是否及格')
    
    correct_count = models.PositiveIntegerField(default=0, verbose_name='正确题数')
    incorrect_count = models.PositiveIntegerField(default=0, verbose_name='错误题数')
    unanswered_count = models.PositiveIntegerField(default=0, verbose_name='未答题数')
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('not_started', '未开始'),
            ('in_progress', '进行中'),
            ('paused', '已暂停'),
            ('submitted', '已提交'),
            ('graded', '已批改'),
            ('absent', '缺考'),
        ],
        default='not_started',
        verbose_name='考试状态'
    )
    
    is_cheating_detected = models.BooleanField(default=False, verbose_name='是否检测到作弊')
    cheating_reason = models.TextField(null=True, blank=True, verbose_name='作弊原因')
    
    submitted_manually = models.BooleanField(default=False, verbose_name='是否手动提交')
    auto_submit_reason = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=[
            ('timeout', '超时自动提交'),
            ('cheating', '作弊自动提交'),
            ('idle', '空闲自动提交'),
        ],
        verbose_name='自动提交原因'
    )
    
    shuffled_questions = models.JSONField(
        default=list,
        verbose_name='随机题目顺序',
        help_text='存储题目ID顺序'
    )
    shuffled_options = models.JSONField(
        default=dict,
        verbose_name='随机选项顺序',
        help_text='{question_id: ["B","A","C","D"]}'
    )
    
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    device_info = models.TextField(null=True, blank=True, verbose_name='设备信息')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '考试记录'
        verbose_name_plural = '考试记录'
        unique_together = ['exam', 'student', 'attempt_number']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['exam', 'status']),
            models.Index(fields=['student', '-created_at']),
        ]

    def __str__(self):
        return f'{self.student.username} - {self.exam.title} (第{self.attempt_number}次)'


class ExamAnswer(models.Model):
    attempt = models.ForeignKey(
        ExamAttempt,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='考试记录'
    )
    question = models.ForeignKey(
        ExamQuestion,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='考试题目'
    )
    
    answer_text = models.TextField(null=True, blank=True, verbose_name='文字答案')
    answer_choice = models.JSONField(
        default=list,
        null=True,
        blank=True,
        verbose_name='选择答案'
    )
    answer_file = models.FileField(
        upload_to='exams/answers/',
        null=True,
        blank=True,
        verbose_name='答案文件'
    )
    
    is_answered = models.BooleanField(default=False, verbose_name='是否作答')
    is_skipped = models.BooleanField(default=False, verbose_name='是否跳过')
    is_flagged = models.BooleanField(default=False, verbose_name='是否标记')
    
    is_correct = models.BooleanField(null=True, blank=True, verbose_name='是否正确')
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='得分'
    )
    partial_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='部分得分'
    )
    
    teacher_feedback = models.TextField(null=True, blank=True, verbose_name='教师评语')
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_answers',
        verbose_name='批改人'
    )
    graded_at = models.DateTimeField(null=True, blank=True, verbose_name='批改时间')
    
    time_spent = models.PositiveIntegerField(null=True, blank=True, verbose_name='用时(秒)')
    last_updated_at = models.DateTimeField(auto_now=True, verbose_name='最后更新时间')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '答题记录'
        verbose_name_plural = '答题记录'
        unique_together = ['attempt', 'question']
        ordering = ['question__question_order']

    def __str__(self):
        return f'{self.attempt.student.username} - Q{self.question.question_order}'


class CheatingRecord(models.Model):
    attempt = models.ForeignKey(
        ExamAttempt,
        on_delete=models.CASCADE,
        related_name='cheating_records',
        verbose_name='考试记录'
    )
    
    cheating_type = models.CharField(
        max_length=50,
        choices=[
            ('tab_switch', '切出页面'),
            ('idle_too_long', '长时间空闲'),
            ('copy_attempt', '尝试复制'),
            ('paste_attempt', '尝试粘贴'),
            ('right_click', '右键操作'),
            ('fullscreen_exit', '退出全屏'),
            ('multiple_logins', '多端登录'),
            ('ip_mismatch', 'IP异常'),
            ('face_verify_fail', '人脸验证失败'),
            ('suspicious_behavior', '可疑行为'),
        ],
        verbose_name='作弊类型'
    )
    
    description = models.TextField(verbose_name='详细描述')
    severity = models.CharField(
        max_length=20,
        choices=[
            ('low', '低'),
            ('medium', '中'),
            ('high', '高'),
            ('critical', '严重'),
        ],
        default='medium',
        verbose_name='严重程度'
    )
    
    evidence = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        verbose_name='证据数据',
        help_text='存储截图信息、操作日志等'
    )
    
    action_taken = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=[
            ('warning', '警告'),
            ('forced_submit', '强制交卷'),
            ('score_zero', '成绩归零'),
            ('ban', '禁止考试'),
            ('none', '无处理'),
        ],
        verbose_name='采取措施'
    )
    
    is_verified = models.BooleanField(default=False, verbose_name='是否已核实')
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_cheatings',
        verbose_name='核实人'
    )
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='核实时间')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='记录时间')

    class Meta:
        verbose_name = '作弊记录'
        verbose_name_plural = '作弊记录'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.attempt.student.username} - {self.get_cheating_type_display()}'


class ExamActivityLog(models.Model):
    attempt = models.ForeignKey(
        ExamAttempt,
        on_delete=models.CASCADE,
        related_name='activity_logs',
        verbose_name='考试记录'
    )
    
    activity_type = models.CharField(
        max_length=50,
        choices=[
            ('start', '开始考试'),
            ('pause', '暂停考试'),
            ('resume', '继续考试'),
            ('submit', '提交试卷'),
            ('answer', '作答题目'),
            ('flag', '标记题目'),
            ('unflag', '取消标记'),
            ('next', '下一题'),
            ('prev', '上一题'),
            ('navigate', '跳转题目'),
            ('tab_leave', '离开页面'),
            ('tab_return', '返回页面'),
            ('idle_start', '开始空闲'),
            ('idle_end', '结束空闲'),
            ('fullscreen_enter', '进入全屏'),
            ('fullscreen_exit', '退出全屏'),
            ('copy_attempt', '尝试复制'),
            ('paste_attempt', '尝试粘贴'),
            ('face_verify', '人脸验证'),
        ],
        verbose_name='活动类型'
    )
    
    details = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        verbose_name='活动详情',
        help_text='如题目ID、用时等'
    )
    
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='时间戳')

    class Meta:
        verbose_name = '考试活动日志'
        verbose_name_plural = '考试活动日志'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['attempt', 'timestamp']),
        ]

    def __str__(self):
        return f'{self.attempt.student.username} - {self.get_activity_type_display()}'
