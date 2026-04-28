import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from datetime import timedelta
from .models import (
    ExamAttempt, ExamActivityLog, CheatingRecord, ExamAnswer, Exam
)


class ExamMonitoringConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close(code=401)
            return
        
        self.attempt_id = self.scope['url_route']['kwargs']['attempt_id']
        
        try:
            self.attempt = await self.get_attempt(self.attempt_id)
        except:
            await self.close(code=404)
            return
        
        if self.attempt.student_id != self.user.id:
            await self.close(code=403)
            return
        
        if self.attempt.status not in ['in_progress', 'paused']:
            await self.close(code=400)
            return
        
        self.exam = await self.get_exam(self.attempt.exam_id)
        
        self.group_name = f'exam_monitoring_{self.attempt_id}'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        self.tab_switch_count = 0
        self.idle_start_time = None
        self.last_activity_time = timezone.now()
        self.in_fullscreen = True
        
        await self.accept()
        
        await self.send(text_data=json.dumps({
            'type': 'connected',
            'data': {
                'anti_cheating_enabled': self.exam.enable_anti_cheating,
                'max_tab_switches': self.exam.get_max_tab_switches(),
                'max_idle_time': self.exam.get_max_idle_time(),
                'require_fullscreen': self.exam.require_fullscreen,
                'block_copy_paste': self.exam.block_copy_paste,
                'block_right_click': self.exam.block_right_click,
                'enable_face_verification': self.exam.enable_face_verification,
                'verify_interval': self.exam.verify_interval
            }
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        
        if hasattr(self, 'attempt') and self.attempt.status == 'in_progress':
            await self.log_activity('disconnect', {'close_code': close_code})

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'heartbeat':
                await self.handle_heartbeat(data.get('data'))
            elif message_type == 'activity':
                await self.handle_activity(data.get('data'))
            elif message_type == 'anti_cheating_event':
                await self.handle_anti_cheating_event(data.get('data'))
            elif message_type == 'answer_update':
                await self.handle_answer_update(data.get('data'))
            elif message_type == 'face_verification':
                await self.handle_face_verification(data.get('data'))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))

    async def handle_heartbeat(self, data):
        self.last_activity_time = timezone.now()
        
        if self.idle_start_time:
            idle_duration = (timezone.now() - self.idle_start_time).total_seconds()
            max_idle_time = self.exam.get_max_idle_time()
            
            if idle_duration > max_idle_time:
                await self.record_cheating(
                    cheating_type='idle_too_long',
                    description=f'长时间空闲，空闲时长: {idle_duration:.1f}秒',
                    severity='medium'
                )
        
        self.idle_start_time = None
        
        await self.log_activity('heartbeat', {})

    async def handle_activity(self, data):
        if not data:
            return
        
        activity_type = data.get('activity_type')
        details = data.get('details', {})
        
        self.last_activity_time = timezone.now()
        self.idle_start_time = None
        
        if activity_type in ['start', 'pause', 'resume', 'submit', 'next', 'prev', 'navigate', 'flag', 'unflag']:
            await self.log_activity(activity_type, details)

    async def handle_anti_cheating_event(self, data):
        if not data or not self.exam.enable_anti_cheating:
            return
        
        event_type = data.get('event_type')
        details = data.get('details', {})
        
        now = timezone.now()
        
        if event_type == 'tab_leave':
            self.tab_switch_count += 1
            await self.log_activity('tab_leave', details)
            
            max_switches = self.exam.get_max_tab_switches()
            if self.tab_switch_count > max_switches:
                await self.record_cheating(
                    cheating_type='tab_switch',
                    description=f'切出页面次数超过限制: {self.tab_switch_count}次',
                    severity='high',
                    evidence={'tab_switch_count': self.tab_switch_count, 'max_allowed': max_switches}
                )
                await self.force_submit('cheating')
        
        elif event_type == 'tab_return':
            await self.log_activity('tab_return', details)
        
        elif event_type == 'fullscreen_exit':
            if self.exam.require_fullscreen:
                self.in_fullscreen = False
                await self.log_activity('fullscreen_exit', details)
                await self.record_cheating(
                    cheating_type='fullscreen_exit',
                    description='考试期间退出全屏模式',
                    severity='medium'
                )
        
        elif event_type == 'fullscreen_enter':
            self.in_fullscreen = True
            await self.log_activity('fullscreen_enter', details)
        
        elif event_type == 'copy_attempt':
            if self.exam.block_copy_paste:
                await self.log_activity('copy_attempt', details)
                await self.record_cheating(
                    cheating_type='copy_attempt',
                    description='考试期间尝试复制内容',
                    severity='low',
                    evidence=details
                )
        
        elif event_type == 'paste_attempt':
            if self.exam.block_copy_paste:
                await self.log_activity('paste_attempt', details)
                await self.record_cheating(
                    cheating_type='paste_attempt',
                    description='考试期间尝试粘贴内容',
                    severity='low',
                    evidence=details
                )
        
        elif event_type == 'right_click':
            if self.exam.block_right_click:
                await self.log_activity('right_click', details)
        
        elif event_type == 'idle_start':
            self.idle_start_time = now
            await self.log_activity('idle_start', details)
        
        elif event_type == 'idle_end':
            if self.idle_start_time:
                idle_duration = (now - self.idle_start_time).total_seconds()
                max_idle_time = self.exam.get_max_idle_time()
                
                if idle_duration > max_idle_time:
                    await self.record_cheating(
                        cheating_type='idle_too_long',
                        description=f'长时间空闲，空闲时长: {idle_duration:.1f}秒',
                        severity='medium',
                        evidence={'idle_duration': idle_duration, 'max_allowed': max_idle_time}
                    )
            
            self.idle_start_time = None
            await self.log_activity('idle_end', {'idle_duration': (now - self.idle_start_time).total_seconds() if self.idle_start_time else 0})
        
        elif event_type == 'suspicious_behavior':
            await self.record_cheating(
                cheating_type='suspicious_behavior',
                description=details.get('description', '检测到可疑行为'),
                severity='medium',
                evidence=details
            )
        
        await self.send(text_data=json.dumps({
            'type': 'anti_cheating_ack',
            'data': {
                'event_type': event_type,
                'tab_switch_count': self.tab_switch_count,
                'max_tab_switches': self.exam.get_max_tab_switches()
            }
        }))

    async def handle_answer_update(self, data):
        if not data:
            return
        
        question_id = data.get('question_id')
        answer_text = data.get('answer_text')
        answer_choice = data.get('answer_choice', [])
        is_skipped = data.get('is_skipped', False)
        is_flagged = data.get('is_flagged', False)
        time_spent = data.get('time_spent')
        
        await self.update_answer(
            question_id=question_id,
            answer_text=answer_text,
            answer_choice=answer_choice,
            is_skipped=is_skipped,
            is_flagged=is_flagged,
            time_spent=time_spent
        )
        
        await self.log_activity('answer', {'question_id': question_id})

    async def handle_face_verification(self, data):
        if not self.exam.enable_face_verification:
            return
        
        verification_data = data.get('verification_data', {})
        is_verified = data.get('is_verified', False)
        
        await self.log_activity('face_verify', {
            'is_verified': is_verified,
            'timestamp': timezone.now().isoformat()
        })
        
        if not is_verified:
            await self.record_cheating(
                cheating_type='face_verify_fail',
                description='人脸验证失败',
                severity='high',
                evidence=verification_data
            )
            await self.force_submit('cheating')
        
        await self.send(text_data=json.dumps({
            'type': 'face_verification_ack',
            'data': {'is_verified': is_verified}
        }))

    async def record_cheating(self, cheating_type, description, severity='medium', evidence=None):
        await database_sync_to_async(self._record_cheating_sync)(
            cheating_type, description, severity, evidence
        )

    def _record_cheating_sync(self, cheating_type, description, severity, evidence):
        cheating = CheatingRecord.objects.create(
            attempt=self.attempt,
            cheating_type=cheating_type,
            description=description,
            severity=severity,
            evidence=evidence or {}
        )
        
        high_severity_types = ['tab_switch', 'face_verify_fail']
        if severity == 'high' or cheating_type in high_severity_types:
            self.attempt.is_cheating_detected = True
            self.attempt.cheating_reason = description
            self.attempt.save()

    async def log_activity(self, activity_type, details):
        await database_sync_to_async(self._log_activity_sync)(activity_type, details)

    def _log_activity_sync(self, activity_type, details):
        ExamActivityLog.objects.create(
            attempt=self.attempt,
            activity_type=activity_type,
            details=details
        )

    async def update_answer(self, question_id, answer_text, answer_choice, is_skipped, is_flagged, time_spent):
        await database_sync_to_async(self._update_answer_sync)(
            question_id, answer_text, answer_choice, is_skipped, is_flagged, time_spent
        )

    def _update_answer_sync(self, question_id, answer_text, answer_choice, is_skipped, is_flagged, time_spent):
        from .models import ExamQuestion
        
        try:
            question = ExamQuestion.objects.get(id=question_id, exam=self.exam)
        except ExamQuestion.DoesNotExist:
            return
        
        answer, created = ExamAnswer.objects.get_or_create(
            attempt=self.attempt,
            question=question,
            defaults={
                'answer_text': answer_text,
                'answer_choice': answer_choice,
                'is_answered': bool(answer_text or answer_choice),
                'is_skipped': is_skipped,
                'is_flagged': is_flagged,
                'time_spent': time_spent
            }
        )
        
        if not created:
            if answer_text is not None:
                answer.answer_text = answer_text
            if answer_choice is not None:
                answer.answer_choice = answer_choice
            if is_skipped is not None:
                answer.is_skipped = is_skipped
            if is_flagged is not None:
                answer.is_flagged = is_flagged
            if time_spent is not None:
                answer.time_spent = time_spent
            answer.is_answered = bool(answer.answer_text or answer.answer_choice)
            answer.save()

    async def force_submit(self, reason):
        await database_sync_to_async(self._force_submit_sync)(reason)
        
        await self.send(text_data=json.dumps({
            'type': 'force_submit',
            'data': {'reason': reason}
        }))
        
        await self.close(code=1000)

    def _force_submit_sync(self, reason):
        from django.utils import timezone
        
        self.attempt.status = 'submitted'
        self.attempt.submitted_manually = False
        self.attempt.auto_submit_reason = reason
        self.attempt.submit_time = timezone.now()
        self.attempt.end_time = timezone.now()
        
        if self.attempt.start_time:
            self.attempt.time_spent = int((self.attempt.end_time - self.attempt.start_time).total_seconds())
        
        self.attempt.save()

    @database_sync_to_async
    def get_attempt(self, attempt_id):
        return ExamAttempt.objects.select_related('exam').get(id=attempt_id)

    @database_sync_to_async
    def get_exam(self, exam_id):
        return Exam.objects.get(id=exam_id)
