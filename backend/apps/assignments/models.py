from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class AssignmentType(models.TextChoices):
    HOMEWORK = 'homework', _('课后作业')
    QUIZ = 'quiz', _('小测验')
    PROJECT = 'project', _('项目作业')
    LAB = 'lab', _('实验报告')


class AssignmentStatus(models.TextChoices):
    DRAFT = 'draft', _('草稿')
    PUBLISHED = 'published', _('已发布')
    CLOSED = 'closed', _('已截止')
    ARCHIVED = 'archived', _('已归档')


class SubmissionStatus(models.TextChoices):
    NOT_SUBMITTED = 'not_submitted', _('未提交')
    SUBMITTED = 'submitted', _('已提交')
    LATE = 'late', _('迟交')
    GRADED = 'graded', _('已批改')
    RETURNED = 'returned', _('已发回')


class GradingStatus(models.TextChoices):
    PENDING = 'pending', _('待批改')
    IN_PROGRESS = 'in_progress', _('批改中')
    COMPLETED = 'completed', _('已完成')
    NEEDS_REVIEW = 'needs_review', _('需复审')


class Assignment(models.Model):
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name='所属课程'
    )
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments',
        verbose_name='所属课时'
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_assignments',
        verbose_name='布置教师'
    )
    
    title = models.CharField(max_length=200, verbose_name='作业标题')
    description = models.TextField(verbose_name='作业描述')
    assignment_type = models.CharField(
        max_length=20,
        choices=AssignmentType.choices,
        default=AssignmentType.HOMEWORK,
        verbose_name='作业类型'
    )
    
    total_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.00, verbose_name='总分')
    pass_score = models.DecimalField(max_digits=5, decimal_places=2, default=60.00, verbose_name='及格分数')
    
    allows_file_upload = models.BooleanField(default=True, verbose_name='允许文件上传')
    allowed_file_types = models.JSONField(
        default=list,
        verbose_name='允许的文件类型',
        help_text='例如: ["pdf", "doc", "docx", "jpg", "png"]'
    )
    max_file_size = models.PositiveIntegerField(default=10, verbose_name='最大文件大小(MB)')
    max_file_count = models.PositiveIntegerField(default=5, verbose_name='最多上传文件数')
    
    allows_text_answer = models.BooleanField(default=True, verbose_name='允许文字作答')
    text_answer_required = models.BooleanField(default=False, verbose_name='文字作答为必填')
    
    start_time = models.DateTimeField(verbose_name='开始时间')
    deadline = models.DateTimeField(verbose_name='截止时间')
    late_deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='迟交截止时间'
    )
    
    allow_late_submission = models.BooleanField(default=False, verbose_name='允许迟交')
    late_submission_penalty = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.10,
        verbose_name='迟交扣分比例',
        help_text='例如: 0.10 表示每迟交一天扣10%'
    )
    
    allow_resubmission = models.BooleanField(default=False, verbose_name='允许重做提交')
    max_resubmissions = models.PositiveIntegerField(default=3, verbose_name='最大重做次数')
    
    is_anonymous_grading = models.BooleanField(default=False, verbose_name='匿名批改')
    show_rubric_to_students = models.BooleanField(default=True, verbose_name='向学生展示评分标准')
    
    status = models.CharField(
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.DRAFT,
        verbose_name='作业状态'
    )
    
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '作业'
        verbose_name_plural = '作业'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['course', 'status']),
            models.Index(fields=['deadline']),
        ]

    def __str__(self):
        return f'{self.course.title} - {self.title}'


class AssignmentQuestion(models.Model):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='作业'
    )
    
    question_text = models.TextField(verbose_name='问题内容')
    question_type = models.CharField(
        max_length=20,
        choices=[
            ('text', '简答题'),
            ('choice', '选择题'),
            ('multi_choice', '多选题'),
            ('file', '文件提交'),
            ('combo', '综合题'),
        ],
        default='text',
        verbose_name='问题类型'
    )
    
    question_order = models.PositiveIntegerField(default=0, verbose_name='题目顺序')
    score = models.DecimalField(max_digits=5, decimal_places=2, default=10.00, verbose_name='分数')
    
    choices = models.JSONField(
        default=list,
        null=True,
        blank=True,
        verbose_name='选项',
        help_text='选择题专用: [{"value": "A", "text": "选项A"}, ...]'
    )
    correct_answer = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        verbose_name='正确答案',
        help_text='选择题答案或参考答案提示'
    )
    
    is_auto_graded = models.BooleanField(default=False, verbose_name='是否自动批改')
    explanation = models.TextField(null=True, blank=True, verbose_name='答案解析')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '作业题目'
        verbose_name_plural = '作业题目'
        ordering = ['question_order']

    def __str__(self):
        return f'Q{self.question_order}: {self.question_text[:50]}'


class GradingRubric(models.Model):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='rubrics',
        verbose_name='作业'
    )
    question = models.ForeignKey(
        AssignmentQuestion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rubrics',
        verbose_name='关联题目'
    )
    
    criterion = models.CharField(max_length=200, verbose_name='评分标准项')
    description = models.TextField(null=True, blank=True, verbose_name='标准描述')
    
    max_score = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='最高分')
    
    levels = models.JSONField(
        default=list,
        verbose_name='评分等级',
        help_text='[{"score": 10, "description": "优秀"}, ...]'
    )
    
    rubric_order = models.PositiveIntegerField(default=0, verbose_name='排序')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '评分标准'
        verbose_name_plural = '评分标准'
        ordering = ['rubric_order']

    def __str__(self):
        return f'{self.assignment.title} - {self.criterion}'


class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions',
        verbose_name='作业'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignment_submissions',
        verbose_name='学生'
    )
    
    text_answer = models.TextField(null=True, blank=True, verbose_name='文字答案')
    
    submission_status = models.CharField(
        max_length=20,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.NOT_SUBMITTED,
        verbose_name='提交状态'
    )
    
    is_late = models.BooleanField(default=False, verbose_name='是否迟交')
    resubmission_count = models.PositiveIntegerField(default=0, verbose_name='重做次数')
    
    total_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='总得分'
    )
    penalty_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='扣分数'
    )
    final_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='最终得分'
    )
    
    grading_status = models.CharField(
        max_length=20,
        choices=GradingStatus.choices,
        default=GradingStatus.PENDING,
        verbose_name='批改状态'
    )
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_submissions',
        verbose_name='批改人'
    )
    graded_at = models.DateTimeField(null=True, blank=True, verbose_name='批改时间')
    
    feedback = models.TextField(null=True, blank=True, verbose_name='整体评语')
    is_returned = models.BooleanField(default=False, verbose_name='是否发回重做')
    
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name='提交时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    submission_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        verbose_name='提交内容哈希',
        help_text='用于幂等性校验'
    )

    class Meta:
        verbose_name = '作业提交'
        verbose_name_plural = '作业提交'
        unique_together = ['assignment', 'student']
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['assignment', 'submission_status']),
            models.Index(fields=['student', '-submitted_at']),
            models.Index(fields=['submission_hash']),
        ]

    def __str__(self):
        return f'{self.student.username} - {self.assignment.title}'

    def calculate_final_score(self):
        if self.total_score is None:
            return None
        return max(0, self.total_score - self.penalty_score)


class SubmissionFile(models.Model):
    submission = models.ForeignKey(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name='提交记录'
    )
    
    file = models.FileField(upload_to='assignments/submissions/', verbose_name='文件')
    filename = models.CharField(max_length=255, verbose_name='文件名')
    file_size = models.BigIntegerField(verbose_name='文件大小(字节)')
    file_type = models.CharField(max_length=50, verbose_name='文件类型')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')

    class Meta:
        verbose_name = '提交文件'
        verbose_name_plural = '提交文件'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.submission.student.username} - {self.filename}'


class AnswerResponse(models.Model):
    submission = models.ForeignKey(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='提交记录'
    )
    question = models.ForeignKey(
        AssignmentQuestion,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name='题目'
    )
    
    answer_text = models.TextField(null=True, blank=True, verbose_name='答案内容')
    answer_choice = models.JSONField(
        default=list,
        null=True,
        blank=True,
        verbose_name='选择答案',
        help_text='选择题答案: ["A", "B"]'
    )
    
    is_auto_graded = models.BooleanField(default=False, verbose_name='是否自动批改')
    is_correct = models.BooleanField(null=True, blank=True, verbose_name='是否正确')
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='得分'
    )
    
    feedback = models.TextField(null=True, blank=True, verbose_name='题目评语')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '答题记录'
        verbose_name_plural = '答题记录'
        unique_together = ['submission', 'question']
        ordering = ['question__question_order']

    def __str__(self):
        return f'{self.submission.student.username} - Q{self.question.question_order}'


class GradingComment(models.Model):
    submission = models.ForeignKey(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name='grading_comments',
        verbose_name='提交记录'
    )
    grader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='grading_comments',
        verbose_name='批改人'
    )
    
    comment = models.TextField(verbose_name='评语内容')
    comment_type = models.CharField(
        max_length=20,
        choices=[
            ('positive', '表扬'),
            ('negative', '批评'),
            ('suggestion', '建议'),
            ('question', '疑问'),
            ('general', '一般'),
        ],
        default='general',
        verbose_name='评语类型'
    )
    
    is_private = models.BooleanField(default=False, verbose_name='是否私密')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '批改评语'
        verbose_name_plural = '批改评语'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.grader.username} - {self.comment[:50]}'


class SubmissionVersion(models.Model):
    submission = models.ForeignKey(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name='提交记录'
    )
    
    version_number = models.PositiveIntegerField(verbose_name='版本号')
    text_answer = models.TextField(null=True, blank=True, verbose_name='文字答案')
    
    files = models.JSONField(
        default=list,
        verbose_name='文件列表',
        help_text='存储文件引用信息'
    )
    answers = models.JSONField(
        default=list,
        verbose_name='答题记录快照'
    )
    
    submitted_at = models.DateTimeField(verbose_name='提交时间')
    
    class Meta:
        verbose_name = '提交版本'
        verbose_name_plural = '提交版本'
        ordering = ['-version_number']
        unique_together = ['submission', 'version_number']

    def __str__(self):
        return f'{self.submission.student.username} - 版本{self.version_number}'
