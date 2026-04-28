import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from datetime import timedelta
from .models import (
    ExamAttempt, ExamActivityLog, CheatingRecord, ExamAnswer, Exam, ExamQuestion
)
import logging

logger = logging.getLogger(__name__)


class ExamMonitoringConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            logger.warning(f"Unauthenticated user tried to connect to exam monitoring")
            await self.close(code=401)
            return
        
        self.attempt_id = self.scope['url_route']['kwargs']['attempt_id']
        
        try:
            self.attempt = await self.get_attempt(self.attempt_id)
        except Exception as e:
            logger.error(f"Failed to get exam attempt {self.attempt_id}: {str(e)}")
            await self.close(code=404)
            return
        
        if self.attempt.student_id != self.user.id:
            logger.warning(f"User {self.user.id} tried to access attempt {self.attempt_id} belonging to user {self.attempt.student_id}")
            await self.close(code=403)
            return
        
        if self.attempt.status not in ['in_progress', 'paused']:
            logger.warning(f"Attempt {self.attempt_id} is not in progress, status: {self.attempt.status}")
            await self.close(code=400)
            return
        
        self.exam = await self.get_exam(self.attempt.exam_id)
        
        self.group_name = f'exam_monitoring_{self.attempt_id}'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        self.tab_switch_count = 0
        self.copy_attempts = 0
        self.paste_attempts = 0
        self.right_click_attempts = 0
        self.fullscreen_exits = 0
        self.idle_violations = 0
        self.total_violations = 0
        self.console_open_attempts = 0
        self.dev_tools_open_attempts = 0
        self.refresh_attempts = 0
        self.close_attempts = 0
        
        self.idle_start_time = None
        self.last_activity_time = timezone.now()
        self.in_fullscreen = True
        self.is_force_submitting = False
        self.is_locked = False
        self.lock_reason = None
        
        self.connected_at = timezone.now()
        
        await self.accept()
        
        await self.log_activity('websocket_connect', {
            'connected_at': self.connected_at.isoformat(),
            'ip_address': self.scope.get('client', [None])[0],
            'user_agent': self.scope.get('headers', [])
        })
        
        await self.send(text_data=json.dumps({
            'type': 'connected',
            'data': {
                'anti_cheating_enabled': self.exam.enable_anti_cheating,
                'max_tab_switches': await self.get_exam_config('max_tab_switches', 3),
                'max_idle_time': await self.get_exam_config('max_idle_time', 300),
                'require_fullscreen': self.exam.require_fullscreen,
                'block_copy_paste': self.exam.block_copy_paste,
                'block_right_click': self.exam.block_right_click,
                'enable_face_verification': self.exam.enable_face_verification,
                'verify_interval': self.exam.verify_interval,
                'current_attempt_status': self.attempt.status,
                'is_locked': self.is_locked
            }
        }))
        
        logger.info(f"User {self.user.id} connected to exam monitoring for attempt {self.attempt_id}")

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        
        if hasattr(self, 'attempt') and self.attempt.status == 'in_progress' and not self.is_locked:
            await self.log_activity('websocket_disconnect', {
                'close_code': close_code,
                'disconnected_at': timezone.now().isoformat(),
                'connected_duration': (timezone.now() - self.connected_at).total_seconds() if hasattr(self, 'connected_at') else 0,
                'tab_switch_count': self.tab_switch_count,
                'total_violations': self.total_violations
            })
        
        logger.info(f"User {self.user.id} disconnected from exam monitoring, close_code: {close_code}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            logger.debug(f"Received message type: {message_type} for attempt {self.attempt_id}")
            
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
            elif message_type == 'beacon_event':
                await self.handle_anti_cheating_event(data.get('data'))
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal server error'
            }))

    @database_sync_to_async
    def get_exam_config(self, key, default):
        if key == 'max_tab_switches':
            return self.exam.max_tab_switches or default
        elif key == 'max_idle_time':
            return self.exam.max_idle_time or default
        return default

    async def handle_heartbeat(self, data):
        self.last_activity_time = timezone.now()
        self.idle_start_time = None
        
        violation_state = data.get('violation_state', {}) if data else {}
        
        if violation_state:
            self.tab_switch_count = violation_state.get('tabSwitchCount', self.tab_switch_count)
            self.copy_attempts = violation_state.get('copyAttempts', self.copy_attempts)
            self.paste_attempts = violation_state.get('pasteAttempts', self.paste_attempts)
            self.fullscreen_exits = violation_state.get('fullscreenExits', self.fullscreen_exits)
            self.idle_violations = violation_state.get('idleViolations', self.idle_violations)
            self.total_violations = violation_state.get('totalViolations', self.total_violations)
            self.console_open_attempts = violation_state.get('consoleOpenAttempts', self.console_open_attempts)
            self.dev_tools_open_attempts = violation_state.get('devToolsOpenAttempts', self.dev_tools_open_attempts)
            self.refresh_attempts = violation_state.get('refreshAttempts', self.refresh_attempts)
        
        is_locked = data.get('is_locked', False) if data else False
        lock_reason = data.get('lock_reason', None) if data else None
        dev_tools_open = data.get('dev_tools_open', False) if data else False
        
        if dev_tools_open and self.dev_tools_open_attempts < 1:
            self.dev_tools_open_attempts = 1
            self.total_violations += 1
        
        if is_locked and not self.is_locked:
            self.is_locked = True
            self.lock_reason = lock_reason
            await self.handle_force_submit('client_lock', lock_reason or '客户端锁定')
        
        max_idle_time = await self.get_exam_config('max_idle_time', 300)
        if self.idle_start_time:
            idle_duration = (timezone.now() - self.idle_start_time).total_seconds()
            
            if idle_duration > max_idle_time:
                self.idle_violations += 1
                self.total_violations += 1
                await self.record_cheating(
                    cheating_type='idle_too_long',
                    description=f'长时间空闲，空闲时长: {idle_duration:.1f}秒',
                    severity='medium',
                    evidence={'idle_duration': idle_duration, 'max_allowed': max_idle_time}
                )
        
        self.idle_start_time = None
        
        await self.log_activity('heartbeat', {
            'timestamp': timezone.now().isoformat(),
            'violation_state': violation_state
        })
        
        await self.send(text_data=json.dumps({
            'type': 'heartbeat_ack',
            'data': {
                'server_time': timezone.now().isoformat(),
                'tab_switch_count': self.tab_switch_count,
                'total_violations': self.total_violations,
                'is_locked': self.is_locked
            }
        }))

    async def handle_activity(self, data):
        if not data:
            return
        
        activity_type = data.get('activity_type')
        details = data.get('details', {})
        
        self.last_activity_time = timezone.now()
        self.idle_start_time = None
        
        valid_activity_types = [
            'start', 'pause', 'resume', 'submit', 'next', 'prev', 
            'navigate', 'flag', 'unflag', 'answer', 'focus', 'blur'
        ]
        
        if activity_type in valid_activity_types:
            await self.log_activity(activity_type, details)

    async def handle_anti_cheating_event(self, data):
        if not data:
            return
        
        if not self.exam.enable_anti_cheating:
            logger.debug(f"Anti-cheating is disabled for exam {self.exam.id}")
            return
        
        event_type = data.get('event_type')
        details = data.get('details', {})
        
        now = timezone.now()
        
        logger.info(f"Anti-cheating event: {event_type} for attempt {self.attempt_id}")
        
        event_handlers = {
            'tab_leave': self._handle_tab_leave,
            'tab_return': self._handle_tab_return,
            'fullscreen_exit': self._handle_fullscreen_exit,
            'fullscreen_enter': self._handle_fullscreen_enter,
            'fullscreen_failed': self._handle_fullscreen_failed,
            'copy_attempt': self._handle_copy_attempt,
            'paste_attempt': self._handle_paste_attempt,
            'cut_attempt': self._handle_cut_attempt,
            'right_click': self._handle_right_click,
            'refresh_attempt': self._handle_refresh_attempt,
            'refresh_detected': self._handle_refresh_detected,
            'print_attempt': self._handle_print_attempt,
            'save_attempt': self._handle_save_attempt,
            'close_attempt': self._handle_close_attempt,
            'escape_press': self._handle_escape_press,
            'idle_start': self._handle_idle_start,
            'idle_too_long': self._handle_idle_too_long,
            'dev_tools_open': self._handle_dev_tools_open,
            'console_open': self._handle_console_open,
            'page_restore': self._handle_page_restore,
            'window_resize': self._handle_window_resize,
            'force_submit_warning': self._handle_force_submit_warning,
            'suspicious_behavior': self._handle_suspicious_behavior,
        }
        
        handler = event_handlers.get(event_type)
        if handler:
            await handler(details)
        else:
            logger.warning(f"Unknown anti-cheating event type: {event_type}")
        
        await self.check_force_submit_condition()
        
        await self.send(text_data=json.dumps({
            'type': 'anti_cheating_ack',
            'data': {
                'event_type': event_type,
                'tab_switch_count': self.tab_switch_count,
                'max_tab_switches': await self.get_exam_config('max_tab_switches', 3),
                'total_violations': self.total_violations,
                'is_locked': self.is_locked,
                'server_time': now.isoformat()
            }
        }))

    async def _handle_tab_leave(self, details):
        self.tab_switch_count = details.get('count', self.tab_switch_count + 1)
        self.total_violations += 1
        self.idle_start_time = timezone.now()
        
        await self.log_activity('tab_leave', details)
        
        max_switches = await self.get_exam_config('max_tab_switches', 3)
        away_duration = details.get('away_duration', 0)
        
        severity = 'high' if self.tab_switch_count >= max_switches else \
                   'medium' if self.tab_switch_count > max_switches / 2 else 'low'
        
        await self.record_cheating(
            cheating_type='tab_switch',
            description=f'切出页面，当前切出次数: {self.tab_switch_count}',
            severity=severity,
            evidence={
                'tab_switch_count': self.tab_switch_count,
                'max_allowed': max_switches,
                'away_duration': away_duration
            }
        )
        
        if self.tab_switch_count >= max_switches:
            await self.force_submit('cheating', f'切出页面次数超过限制({max_switches}次)')
        else:
            await self.send_warning(
                f'检测到切出页面，剩余切出次数: {max_switches - self.tab_switch_count}'
            )

    async def _handle_tab_return(self, details):
        self.idle_start_time = None
        self.last_activity_time = timezone.now()
        await self.log_activity('tab_return', details)

    async def _handle_fullscreen_exit(self, details):
        if not self.exam.require_fullscreen:
            return
        
        self.in_fullscreen = False
        self.fullscreen_exits = details.get('count', self.fullscreen_exits + 1)
        self.total_violations += 1
        
        await self.log_activity('fullscreen_exit', details)
        await self.record_cheating(
            cheating_type='fullscreen_exit',
            description='考试期间退出全屏模式',
            severity='medium',
            evidence={'count': self.fullscreen_exits}
        )

    async def _handle_fullscreen_enter(self, details):
        self.in_fullscreen = True
        await self.log_activity('fullscreen_enter', details)

    async def _handle_fullscreen_failed(self, details):
        await self.log_activity('fullscreen_failed', details)
        await self.record_cheating(
            cheating_type='fullscreen_failed',
            description='无法进入全屏模式',
            severity='low',
            evidence=details
        )

    async def _handle_copy_attempt(self, details):
        if not self.exam.block_copy_paste:
            return
        
        self.copy_attempts = details.get('count', self.copy_attempts + 1)
        self.total_violations += 1
        
        await self.log_activity('copy_attempt', details)
        await self.record_cheating(
            cheating_type='copy_attempt',
            description='考试期间尝试复制内容',
            severity='low',
            evidence={'count': self.copy_attempts}
        )

    async def _handle_paste_attempt(self, details):
        if not self.exam.block_copy_paste:
            return
        
        self.paste_attempts = details.get('count', self.paste_attempts + 1)
        self.total_violations += 1
        
        await self.log_activity('paste_attempt', details)
        await self.record_cheating(
            cheating_type='paste_attempt',
            description='考试期间尝试粘贴内容',
            severity='low',
            evidence={'count': self.paste_attempts}
        )

    async def _handle_cut_attempt(self, details):
        if not self.exam.block_copy_paste:
            return
        
        self.right_click_attempts += 1
        self.total_violations += 1
        
        await self.log_activity('cut_attempt', details)
        await self.record_cheating(
            cheating_type='cut_attempt',
            description='考试期间尝试剪切内容',
            severity='low'
        )

    async def _handle_right_click(self, details):
        if not self.exam.block_right_click:
            return
        
        self.right_click_attempts = details.get('count', self.right_click_attempts + 1)
        self.total_violations += 1
        
        await self.log_activity('right_click', details)
        await self.record_cheating(
            cheating_type='right_click',
            description='考试期间尝试打开右键菜单',
            severity='low',
            evidence={'count': self.right_click_attempts}
        )

    async def _handle_refresh_attempt(self, details):
        self.refresh_attempts = details.get('count', self.refresh_attempts + 1)
        self.total_violations += 1
        
        detection_method = details.get('detection_method', 'unknown')
        description = f'考试期间尝试刷新页面（{detection_method}）'
        
        await self.log_activity('refresh_attempt', details)
        await self.record_cheating(
            cheating_type='refresh_attempt',
            description=description,
            severity='medium',
            evidence={
                'count': self.refresh_attempts,
                'detection_method': detection_method
            }
        )
        
        max_refresh = 2
        if self.refresh_attempts >= max_refresh:
            await self.force_submit('cheating', f'刷新页面超过限制({max_refresh}次)')

    async def _handle_refresh_detected(self, details):
        self.refresh_attempts = details.get('count', self.refresh_attempts + 1)
        self.total_violations += 1
        
        time_since_last = details.get('time_since_last', 0)
        
        await self.log_activity('refresh_detected', details)
        await self.record_cheating(
            cheating_type='refresh_detected',
            description='检测到页面刷新',
            severity='medium',
            evidence={
                'count': self.refresh_attempts,
                'time_since_last': time_since_last
            }
        )

    async def _handle_print_attempt(self, details):
        self.total_violations += 1
        
        await self.log_activity('print_attempt', details)
        await self.record_cheating(
            cheating_type='print_attempt',
            description='考试期间尝试打印页面',
            severity='low'
        )

    async def _handle_save_attempt(self, details):
        self.total_violations += 1
        
        await self.log_activity('save_attempt', details)
        await self.record_cheating(
            cheating_type='save_attempt',
            description='考试期间尝试保存页面',
            severity='low'
        )

    async def _handle_close_attempt(self, details):
        self.close_attempts += 1
        self.total_violations += 1
        
        await self.log_activity('close_attempt', details)
        await self.record_cheating(
            cheating_type='close_attempt',
            description='考试期间尝试关闭标签页',
            severity='high'
        )

    async def _handle_escape_press(self, details):
        if self.exam.require_fullscreen:
            self.total_violations += 1
            
            await self.log_activity('escape_press', details)
            await self.record_cheating(
                cheating_type='escape_press',
                description='考试期间尝试通过Escape退出全屏',
                severity='medium'
            )

    async def _handle_idle_start(self, details):
        self.idle_start_time = timezone.now()
        await self.log_activity('idle_start', details)

    async def _handle_idle_too_long(self, details):
        self.idle_violations += 1
        self.total_violations += 1
        
        idle_duration = details.get('idle_duration', 0)
        max_allowed = details.get('max_allowed', 0)
        
        await self.record_cheating(
            cheating_type='idle_too_long',
            description=f'长时间空闲，空闲时长: {idle_duration:.1f}秒',
            severity='medium',
            evidence={'idle_duration': idle_duration, 'max_allowed': max_allowed}
        )

    async def _handle_dev_tools_open(self, details):
        self.dev_tools_open_attempts = details.get('count', self.dev_tools_open_attempts + 1)
        self.total_violations += 1
        
        detection_method = details.get('detection_method', 'unknown')
        description = f'检测到开发者工具已打开（{detection_method}检测）'
        
        await self.log_activity('dev_tools_open', details)
        await self.record_cheating(
            cheating_type='dev_tools_open',
            description=description,
            severity='high',
            evidence={
                'count': self.dev_tools_open_attempts,
                'detection_method': detection_method
            }
        )
        
        max_dev_tools = 2
        if self.dev_tools_open_attempts >= max_dev_tools:
            await self.force_submit('cheating', f'开发者工具打开超过限制({max_dev_tools}次)')

    async def _handle_console_open(self, details):
        self.console_open_attempts = details.get('count', self.console_open_attempts + 1)
        self.total_violations += 1
        
        await self.log_activity('console_open', details)
        await self.record_cheating(
            cheating_type='console_open',
            description='检测到控制台被打开',
            severity='medium',
            evidence={'count': self.console_open_attempts}
        )

    async def _handle_page_restore(self, details):
        self.total_violations += 1
        
        await self.log_activity('page_restore', details)
        await self.record_cheating(
            cheating_type='page_restore',
            description='检测到页面从缓存中恢复（可能是刷新或后退操作）',
            severity='medium',
            evidence=details
        )

    async def _handle_window_resize(self, details):
        if self.exam.require_fullscreen:
            await self.log_activity('window_resize', details)
            await self.record_cheating(
                cheating_type='window_resize',
                description='检测到窗口大小变化',
                severity='low',
                evidence=details
            )

    async def _handle_force_submit_warning(self, details):
        await self.log_activity('force_submit_warning', details)

    async def _handle_suspicious_behavior(self, details):
        self.total_violations += 1
        
        description = details.get('description', '检测到可疑行为')
        await self.record_cheating(
            cheating_type='suspicious_behavior',
            description=description,
            severity='medium',
            evidence=details
        )

    async def check_force_submit_condition(self):
        if self.is_force_submitting or self.is_locked:
            return
        
        max_violations = 10
        max_tab_switches = await self.get_exam_config('max_tab_switches', 3)
        max_refresh = 2
        max_dev_tools = 2
        
        should_force_submit = False
        reason = ''
        
        if self.tab_switch_count >= max_tab_switches:
            should_force_submit = True
            reason = f'切出页面次数超过限制({max_tab_switches}次)'
        elif self.refresh_attempts >= max_refresh:
            should_force_submit = True
            reason = f'刷新页面超过限制({max_refresh}次)'
        elif self.dev_tools_open_attempts >= max_dev_tools:
            should_force_submit = True
            reason = f'开发者工具打开超过限制({max_dev_tools}次)'
        elif self.total_violations >= max_violations:
            should_force_submit = True
            reason = f'违规次数超过限制({max_violations}次)'
        
        if should_force_submit:
            await self.force_submit('cheating', reason)

    async def handle_answer_update(self, data):
        if not data:
            return
        
        question_id = data.get('question_id')
        answer_text = data.get('answer_text')
        answer_choice = data.get('answer_choice', [])
        is_skipped = data.get('is_skipped', False)
        is_flagged = data.get('is_flagged', False)
        time_spent = data.get('time_spent')
        
        self.last_activity_time = timezone.now()
        self.idle_start_time = None
        
        await self.update_answer(
            question_id=question_id,
            answer_text=answer_text,
            answer_choice=answer_choice,
            is_skipped=is_skipped,
            is_flagged=is_flagged,
            time_spent=time_spent
        )
        
        await self.log_activity('answer', {
            'question_id': question_id,
            'is_answered': bool(answer_text or answer_choice),
            'is_skipped': is_skipped,
            'is_flagged': is_flagged
        })

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
            await self.force_submit('cheating', '人脸验证失败')
        
        await self.send(text_data=json.dumps({
            'type': 'face_verification_ack',
            'data': {'is_verified': is_verified}
        }))

    async def send_warning(self, message):
        await self.send(text_data=json.dumps({
            'type': 'warning',
            'message': message,
            'data': {
                'tab_switch_count': self.tab_switch_count,
                'max_tab_switches': await self.get_exam_config('max_tab_switches', 3),
                'total_violations': self.total_violations,
                'server_time': timezone.now().isoformat()
            }
        }))

    @database_sync_to_async
    def record_cheating(self, cheating_type, description, severity='medium', evidence=None):
        from django.db import transaction
        
        try:
            with transaction.atomic():
                cheating = CheatingRecord.objects.create(
                    attempt=self.attempt,
                    cheating_type=cheating_type,
                    description=description,
                    severity=severity,
                    evidence=evidence or {}
                )
                
                high_severity_types = [
                    'tab_switch', 'face_verify_fail', 'dev_tools_open',
                    'refresh_detected', 'close_attempt'
                ]
                
                if severity == 'high' or cheating_type in high_severity_types:
                    self.attempt.is_cheating_detected = True
                    
                    if not self.attempt.cheating_reason:
                        self.attempt.cheating_reason = description
                    else:
                        self.attempt.cheating_reason = f"{self.attempt.cheating_reason}; {description}"
                    
                    self.attempt.save(update_fields=['is_cheating_detected', 'cheating_reason'])
                
                logger.info(f"Cheating record created: {cheating_type} for attempt {self.attempt_id}")
                return cheating
                
        except Exception as e:
            logger.error(f"Failed to record cheating: {str(e)}", exc_info=True)
            raise

    @database_sync_to_async
    def log_activity(self, activity_type, details):
        try:
            ExamActivityLog.objects.create(
                attempt=self.attempt,
                activity_type=activity_type,
                details=details or {}
            )
            logger.debug(f"Activity logged: {activity_type} for attempt {self.attempt_id}")
        except Exception as e:
            logger.error(f"Failed to log activity: {str(e)}")

    @database_sync_to_async
    def update_answer(self, question_id, answer_text, answer_choice, is_skipped, is_flagged, time_spent):
        from django.db import transaction
        
        try:
            with transaction.atomic():
                try:
                    question = ExamQuestion.objects.get(id=question_id, exam=self.exam)
                except ExamQuestion.DoesNotExist:
                    logger.warning(f"Question {question_id} not found for exam {self.exam.id}")
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
                
                logger.debug(f"Answer updated for question {question_id}, attempt {self.attempt_id}")
                
        except Exception as e:
            logger.error(f"Failed to update answer: {str(e)}", exc_info=True)

    async def handle_force_submit(self, reason, description):
        await self.force_submit(reason, description)

    async def force_submit(self, reason, description=None):
        if self.is_force_submitting:
            return
        
        self.is_force_submitting = True
        self.is_locked = True
        self.lock_reason = description or reason
        
        logger.warning(f"Force submitting attempt {self.attempt_id}, reason: {reason}")
        
        await database_sync_to_async(self._force_submit_sync)(reason, description)
        
        await self.send(text_data=json.dumps({
            'type': 'force_submit',
            'data': {
                'reason': reason,
                'description': description or '系统检测到违规行为',
                'is_locked': self.is_locked,
                'server_time': timezone.now().isoformat()
            }
        }))
        
        await self.close(code=1000)

    def _force_submit_sync(self, reason, description):
        from django.db import transaction
        
        try:
            with transaction.atomic():
                self.attempt.refresh_from_db()
                
                if self.attempt.status not in ['in_progress', 'paused']:
                    logger.warning(f"Attempt {self.attempt_id} is not in progress, status: {self.attempt.status}")
                    return
                
                now = timezone.now()
                
                self.attempt.status = 'submitted'
                self.attempt.submitted_manually = False
                self.attempt.auto_submit_reason = reason
                self.attempt.submit_time = now
                self.attempt.end_time = now
                
                if self.attempt.start_time:
                    self.attempt.time_spent = int(
                        (self.attempt.end_time - self.attempt.start_time).total_seconds()
                    )
                
                self.attempt.is_cheating_detected = True
                self.attempt.cheating_reason = description or f'自动提交原因: {reason}'
                
                self.attempt.save()
                
                CheatingRecord.objects.create(
                    attempt=self.attempt,
                    cheating_type='auto_submit',
                    description=description or f'系统自动提交，原因: {reason}',
                    severity='high',
                    action_taken='forced_submit'
                )
                
                logger.info(f"Attempt {self.attempt_id} force submitted successfully")
                
        except Exception as e:
            logger.error(f"Failed to force submit attempt {self.attempt_id}: {str(e)}", exc_info=True)
            raise

    @database_sync_to_async
    def get_attempt(self, attempt_id):
        from django.db.models import select_related
        return ExamAttempt.objects.select_related('exam', 'student').get(id=attempt_id)

    @database_sync_to_async
    def get_exam(self, exam_id):
        return Exam.objects.get(id=exam_id)
