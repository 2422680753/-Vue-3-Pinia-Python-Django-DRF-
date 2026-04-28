import { Ref, ref, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { examMonitoringSocket } from './websocket'

interface AntiCheatingConfig {
  maxTabSwitches: number
  maxIdleTime: number
  requireFullscreen: boolean
  blockCopyPaste: boolean
  blockRightClick: boolean
  enableFaceVerification: boolean
  verifyInterval: number
  maxViolations: number
  violationThreshold: Record<string, number>
}

interface CheatingEvent {
  eventType: string
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  timestamp: Date
  details?: Record<string, any>
}

interface ViolationState {
  tabSwitchCount: number
  copyAttempts: number
  pasteAttempts: number
  rightClickAttempts: number
  fullscreenExits: number
  idleViolations: number
  totalViolations: number
}

interface PendingEvent {
  type: string
  data: any
  timestamp: number
  retryCount: number
}

const STORAGE_KEYS = {
  PENDING_EVENTS: 'exam_pending_events',
  VIOLATION_STATE: 'exam_violation_state',
  SESSION_START: 'exam_session_start',
  LAST_ACTIVITY: 'exam_last_activity'
}

class ExamAntiCheating {
  private attemptId: number | null = null
  private examId: number | null = null
  private config: AntiCheatingConfig = {
    maxTabSwitches: 3,
    maxIdleTime: 300,
    requireFullscreen: true,
    blockCopyPaste: true,
    blockRightClick: true,
    enableFaceVerification: false,
    verifyInterval: 600,
    maxViolations: 10,
    violationThreshold: {
      tab_switch: 3,
      copy_attempt: 5,
      paste_attempt: 5,
      fullscreen_exit: 3,
      idle_too_long: 2
    }
  }

  private violationState: ViolationState = {
    tabSwitchCount: 0,
    copyAttempts: 0,
    pasteAttempts: 0,
    rightClickAttempts: 0,
    fullscreenExits: 0,
    idleViolations: 0,
    totalViolations: 0
  }

  private idleStartTime: Date | null = null
  private lastActivityTime: Date = new Date()
  private inFullscreen: boolean = true
  private isMonitoring: boolean = false
  private isInitialized: boolean = false
  private events: CheatingEvent[] = []
  private pendingEvents: PendingEvent[] = []
  private isForceSubmitting: boolean = false

  private boundHandlers: {
    visibilityChange: () => void
    fullscreenChange: () => void
    copy: (e: ClipboardEvent) => void
    paste: (e: ClipboardEvent) => void
    cut: (e: ClipboardEvent) => void
    contextMenu: (e: MouseEvent) => void
    activity: (e: Event) => void
    beforeUnload: (e: BeforeUnloadEvent) => string | undefined
    keydown: (e: KeyboardEvent) => void
    pageHide: () => void
  } | null = null

  private idleCheckInterval: number | null = null
  private faceVerifyInterval: number | null = null
  private pendingRetryInterval: number | null = null

  public onCheatingDetected: ((event: CheatingEvent) => void) | null = null
  public onForceSubmit: (() => void) | null = null
  public onWarning: ((message: string, remaining: number) => void) | null = null

  init(attemptId: number, examId?: number, config?: Partial<AntiCheatingConfig>) {
    this.attemptId = attemptId
    this.examId = examId || null
    this.config = { ...this.config, ...config }
    this.isForceSubmitting = false

    this.loadStateFromStorage()
    this.resetViolationState()

    this.events = []
    this.isMonitoring = true
    this.isInitialized = true

    this.bindEventListeners()
    this.startIdleCheck()
    this.startPendingRetry()

    if (this.config.enableFaceVerification) {
      this.startFaceVerification()
    }

    if (this.config.requireFullscreen) {
      this.enterFullscreen()
    }

    this.saveToStorage(STORAGE_KEYS.SESSION_START, new Date().toISOString())

    console.log('Exam anti-cheating initialized for attempt:', attemptId)
  }

  private resetViolationState() {
    this.violationState = {
      tabSwitchCount: 0,
      copyAttempts: 0,
      pasteAttempts: 0,
      rightClickAttempts: 0,
      fullscreenExits: 0,
      idleViolations: 0,
      totalViolations: 0
    }
    this.tabSwitchCount = 0
    this.idleStartTime = null
    this.lastActivityTime = new Date()
    this.inFullscreen = true
  }

  private loadStateFromStorage() {
    try {
      const pending = localStorage.getItem(STORAGE_KEYS.PENDING_EVENTS)
      if (pending) {
        this.pendingEvents = JSON.parse(pending)
      }

      const violation = localStorage.getItem(STORAGE_KEYS.VIOLATION_STATE)
      if (violation) {
        this.violationState = JSON.parse(violation)
        this.tabSwitchCount = this.violationState.tabSwitchCount
      }

      const lastActivity = localStorage.getItem(STORAGE_KEYS.LAST_ACTIVITY)
      if (lastActivity) {
        this.lastActivityTime = new Date(lastActivity)
      }
    } catch (e) {
      console.warn('Failed to load anti-cheating state:', e)
    }
  }

  private saveToStorage(key: string, value: any) {
    try {
      localStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value))
    } catch (e) {
      console.warn('Failed to save to storage:', e)
    }
  }

  private removeFromStorage(key: string) {
    try {
      localStorage.removeItem(key)
    } catch (e) {
      console.warn('Failed to remove from storage:', e)
    }
  }

  private clearStorage() {
    Object.values(STORAGE_KEYS).forEach(key => this.removeFromStorage(key))
  }

  private bindEventListeners() {
    this.boundHandlers = {
      visibilityChange: this.handleVisibilityChange.bind(this),
      fullscreenChange: this.handleFullscreenChange.bind(this),
      copy: this.handleCopy.bind(this),
      paste: this.handlePaste.bind(this),
      cut: this.handleCut.bind(this),
      contextMenu: this.handleContextMenu.bind(this),
      activity: this.handleActivity.bind(this),
      beforeUnload: this.handleBeforeUnload.bind(this),
      keydown: this.handleKeyDown.bind(this),
      pageHide: this.handlePageHide.bind(this)
    }

    document.addEventListener('visibilitychange', this.boundHandlers.visibilityChange)
    document.addEventListener('fullscreenchange', this.boundHandlers.fullscreenChange)

    if (this.config.blockCopyPaste) {
      document.addEventListener('copy', this.boundHandlers.copy)
      document.addEventListener('paste', this.boundHandlers.paste)
      document.addEventListener('cut', this.boundHandlers.cut)
    }

    if (this.config.blockRightClick) {
      document.addEventListener('contextmenu', this.boundHandlers.contextMenu)
    }

    window.addEventListener('mousemove', this.boundHandlers.activity)
    window.addEventListener('keydown', this.boundHandlers.keydown)
    window.addEventListener('click', this.boundHandlers.activity)
    window.addEventListener('scroll', this.boundHandlers.activity)
    window.addEventListener('touchstart', this.boundHandlers.activity)
    window.addEventListener('touchmove', this.boundHandlers.activity)

    window.addEventListener('beforeunload', this.boundHandlers.beforeUnload)
    window.addEventListener('pagehide', this.boundHandlers.pageHide)
  }

  private unbindEventListeners() {
    if (!this.boundHandlers) return

    document.removeEventListener('visibilitychange', this.boundHandlers.visibilityChange)
    document.removeEventListener('fullscreenchange', this.boundHandlers.fullscreenChange)
    document.removeEventListener('copy', this.boundHandlers.copy)
    document.removeEventListener('paste', this.boundHandlers.paste)
    document.removeEventListener('cut', this.boundHandlers.cut)
    document.removeEventListener('contextmenu', this.boundHandlers.contextMenu)

    window.removeEventListener('mousemove', this.boundHandlers.activity)
    window.removeEventListener('keydown', this.boundHandlers.keydown)
    window.removeEventListener('click', this.boundHandlers.activity)
    window.removeEventListener('scroll', this.boundHandlers.activity)
    window.removeEventListener('touchstart', this.boundHandlers.activity)
    window.removeEventListener('touchmove', this.boundHandlers.activity)

    window.removeEventListener('beforeunload', this.boundHandlers.beforeUnload)
    window.removeEventListener('pagehide', this.boundHandlers.pageHide)
  }

  private startIdleCheck() {
    this.idleCheckInterval = window.setInterval(() => {
      if (!this.isMonitoring) return

      const now = new Date()
      const idleTime = (now.getTime() - this.lastActivityTime.getTime()) / 1000

      if (idleTime > this.config.maxIdleTime) {
        if (!this.idleStartTime) {
          this.idleStartTime = new Date()
          this.sendAntiCheatingEvent('idle_start', {
            idle_duration: idleTime,
            max_allowed: this.config.maxIdleTime
          })
        }

        const totalIdleTime = (now.getTime() - this.idleStartTime.getTime()) / 1000
        if (totalIdleTime > this.config.maxIdleTime * 2) {
          this.violationState.idleViolations++
          this.violationState.totalViolations++
          this.saveViolationState()

          this.recordCheatingEvent(
            'idle_too_long',
            `长时间空闲，空闲时长: ${totalIdleTime.toFixed(1)}秒`,
            'medium',
            { idle_duration: totalIdleTime, max_allowed: this.config.maxIdleTime }
          )

          this.sendAntiCheatingEvent('idle_too_long', {
            idle_duration: totalIdleTime,
            max_allowed: this.config.maxIdleTime
          })

          this.checkForceSubmitCondition('idle_too_long')
        }
      }
    }, 5000)
  }

  private stopIdleCheck() {
    if (this.idleCheckInterval) {
      clearInterval(this.idleCheckInterval)
      this.idleCheckInterval = null
    }
  }

  private startFaceVerification() {
    this.faceVerifyInterval = window.setInterval(() => {
      this.requestFaceVerification()
    }, this.config.verifyInterval * 1000)

    setTimeout(() => this.requestFaceVerification(), 5000)
  }

  private stopFaceVerification() {
    if (this.faceVerifyInterval) {
      clearInterval(this.faceVerifyInterval)
      this.faceVerifyInterval = null
    }
  }

  private startPendingRetry() {
    this.pendingRetryInterval = window.setInterval(() => {
      this.retryPendingEvents()
    }, 10000)
  }

  private stopPendingRetry() {
    if (this.pendingRetryInterval) {
      clearInterval(this.pendingRetryInterval)
      this.pendingRetryInterval = null
    }
  }

  private async retryPendingEvents() {
    if (this.pendingEvents.length === 0) return

    const toRetry = [...this.pendingEvents]
    this.pendingEvents = []

    for (const event of toRetry) {
      if (event.retryCount < 5) {
        const success = this.sendToWebSocket(event.type, event.data)
        if (!success) {
          event.retryCount++
          this.pendingEvents.push(event)
        }
      }
    }

    this.savePendingEvents()
  }

  private savePendingEvents() {
    this.saveToStorage(STORAGE_KEYS.PENDING_EVENTS, this.pendingEvents)
  }

  private saveViolationState() {
    this.saveToStorage(STORAGE_KEYS.VIOLATION_STATE, this.violationState)
  }

  private handleVisibilityChange() {
    if (!this.isMonitoring || this.isForceSubmitting) return

    if (document.hidden) {
      this.violationState.tabSwitchCount++
      this.tabSwitchCount = this.violationState.tabSwitchCount
      this.violationState.totalViolations++
      this.idleStartTime = new Date()

      this.saveViolationState()

      const severity: 'low' | 'medium' | 'high' = 
        this.violationState.tabSwitchCount > this.config.maxTabSwitches ? 'high' :
        this.violationState.tabSwitchCount > this.config.maxTabSwitches / 2 ? 'medium' : 'low'

      this.recordCheatingEvent(
        'tab_switch',
        `切出页面，当前切出次数: ${this.violationState.tabSwitchCount}`,
        severity,
        { count: this.violationState.tabSwitchCount, max_allowed: this.config.maxTabSwitches }
      )

      this.sendAntiCheatingEvent('tab_leave', {
        count: this.violationState.tabSwitchCount,
        max_allowed: this.config.maxTabSwitches
      })

      if (this.violationState.tabSwitchCount >= this.config.maxTabSwitches) {
        this.checkForceSubmitCondition('tab_switch')
      } else {
        const remaining = this.config.maxTabSwitches - this.violationState.tabSwitchCount
        ElMessage.warning({
          message: `检测到切出页面，剩余切出次数: ${remaining}`,
          duration: 3000
        })
        this.onWarning?.(`切出页面次数: ${this.violationState.tabSwitchCount}/${this.config.maxTabSwitches}`, remaining)
      }
    } else {
      this.lastActivityTime = new Date()
      this.idleStartTime = null
      this.saveToStorage(STORAGE_KEYS.LAST_ACTIVITY, new Date().toISOString())

      this.sendAntiCheatingEvent('tab_return', {
        count: this.violationState.tabSwitchCount
      })
    }
  }

  private handleFullscreenChange() {
    if (!this.isMonitoring || this.isForceSubmitting) return

    const isFullscreen = !!document.fullscreenElement

    if (!isFullscreen && this.config.requireFullscreen) {
      this.inFullscreen = false
      this.violationState.fullscreenExits++
      this.violationState.totalViolations++
      this.saveViolationState()

      this.recordCheatingEvent(
        'fullscreen_exit',
        '考试期间退出全屏模式',
        'medium',
        { count: this.violationState.fullscreenExits }
      )

      this.sendAntiCheatingEvent('fullscreen_exit', {
        count: this.violationState.fullscreenExits
      })

      ElMessage.warning('请保持全屏模式进行考试，系统将尝试重新进入全屏')

      setTimeout(() => {
        if (!document.fullscreenElement && this.isMonitoring) {
          this.enterFullscreen()
        }
      }, 1000)
    } else {
      this.inFullscreen = true
      this.sendAntiCheatingEvent('fullscreen_enter', {})
    }
  }

  private handleCopy(e: ClipboardEvent) {
    if (!this.isMonitoring || this.isForceSubmitting) return

    if (!this.isAllowedCopyTarget(e.target as HTMLElement)) {
      e.preventDefault()
      e.stopPropagation()

      this.violationState.copyAttempts++
      this.violationState.totalViolations++
      this.saveViolationState()

      this.recordCheatingEvent(
        'copy_attempt',
        '考试期间尝试复制内容',
        'low',
        { count: this.violationState.copyAttempts }
      )

      this.sendAntiCheatingEvent('copy_attempt', {
        timestamp: new Date().toISOString(),
        count: this.violationState.copyAttempts
      })

      ElMessage.warning('考试期间禁止复制')
    }
  }

  private handlePaste(e: ClipboardEvent) {
    if (!this.isMonitoring || this.isForceSubmitting) return

    if (!this.isAllowedPasteTarget(e.target as HTMLElement)) {
      e.preventDefault()
      e.stopPropagation()

      this.violationState.pasteAttempts++
      this.violationState.totalViolations++
      this.saveViolationState()

      this.recordCheatingEvent(
        'paste_attempt',
        '考试期间尝试粘贴内容',
        'low',
        { count: this.violationState.pasteAttempts }
      )

      this.sendAntiCheatingEvent('paste_attempt', {
        timestamp: new Date().toISOString(),
        count: this.violationState.pasteAttempts
      })

      ElMessage.warning('考试期间禁止粘贴')
    }
  }

  private handleCut(e: ClipboardEvent) {
    if (!this.isMonitoring || this.isForceSubmitting) return

    e.preventDefault()
    e.stopPropagation()

    this.violationState.rightClickAttempts++
    this.violationState.totalViolations++
    this.saveViolationState()

    this.recordCheatingEvent(
      'cut_attempt',
      '考试期间尝试剪切内容',
      'low'
    )

    this.sendAntiCheatingEvent('cut_attempt', {
      timestamp: new Date().toISOString()
    })

    ElMessage.warning('考试期间禁止剪切')
  }

  private handleContextMenu(e: MouseEvent) {
    if (!this.isMonitoring || this.isForceSubmitting) return

    e.preventDefault()
    e.stopPropagation()

    this.violationState.rightClickAttempts++
    this.saveViolationState()

    this.sendAntiCheatingEvent('right_click', {
      timestamp: new Date().toISOString(),
      count: this.violationState.rightClickAttempts
    })
  }

  private handleKeyDown(e: KeyboardEvent) {
    if (!this.isMonitoring || this.isForceSubmitting) return

    this.lastActivityTime = new Date()
    this.saveToStorage(STORAGE_KEYS.LAST_ACTIVITY, new Date().toISOString())

    if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
      if (!this.isAllowedCopyTarget(e.target as HTMLElement)) {
        e.preventDefault()
        e.stopPropagation()
        this.handleCopy(e as any)
      }
    }

    if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
      if (!this.isAllowedPasteTarget(e.target as HTMLElement)) {
        e.preventDefault()
        e.stopPropagation()
        this.handlePaste(e as any)
      }
    }

    if ((e.ctrlKey || e.metaKey) && e.key === 'x') {
      e.preventDefault()
      e.stopPropagation()
      this.handleCut(e as any)
    }

    if (e.key === 'F5' || ((e.ctrlKey || e.metaKey) && e.key === 'r')) {
      if (!e.shiftKey) {
        e.preventDefault()
        this.recordCheatingEvent(
          'refresh_attempt',
          '考试期间尝试刷新页面',
          'medium'
        )
        this.sendAntiCheatingEvent('refresh_attempt', {
          timestamp: new Date().toISOString()
        })
        ElMessage.warning('考试期间禁止刷新页面')
      }
    }

    if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
      e.preventDefault()
      this.recordCheatingEvent(
        'print_attempt',
        '考试期间尝试打印页面',
        'medium'
      )
      this.sendAntiCheatingEvent('print_attempt', {
        timestamp: new Date().toISOString()
      })
      ElMessage.warning('考试期间禁止打印')
    }

    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault()
      this.recordCheatingEvent(
        'save_attempt',
        '考试期间尝试保存页面',
        'medium'
      )
      this.sendAntiCheatingEvent('save_attempt', {
        timestamp: new Date().toISOString()
      })
    }

    if (e.key === 'Escape') {
      if (document.fullscreenElement && this.config.requireFullscreen) {
        e.preventDefault()
      }
    }
  }

  private handleActivity(e: Event) {
    if (!this.isMonitoring) return

    this.lastActivityTime = new Date()
    this.idleStartTime = null
    this.saveToStorage(STORAGE_KEYS.LAST_ACTIVITY, new Date().toISOString())
  }

  private handleBeforeUnload(e: BeforeUnloadEvent): string | undefined {
    if (!this.isMonitoring || this.isForceSubmitting) return

    this.sendEventViaBeacon('before_unload', {
      timestamp: new Date().toISOString()
    })

    const message = '考试进行中，确定要离开吗？离开后考试将被提交！'
    e.preventDefault()
    e.returnValue = message
    return message
  }

  private handlePageHide() {
    if (!this.isMonitoring) return

    this.sendEventViaBeacon('page_hide', {
      timestamp: new Date().toISOString(),
      violation_state: this.violationState,
      last_activity: this.lastActivityTime.toISOString()
    })
  }

  private isAllowedCopyTarget(target: HTMLElement | null): boolean {
    if (!target) return false

    const allowedTags = ['INPUT', 'TEXTAREA']
    if (allowedTags.includes(target.tagName)) {
      return true
    }

    const isContentEditable = target.isContentEditable
    return isContentEditable
  }

  private isAllowedPasteTarget(target: HTMLElement | null): boolean {
    if (!target) return false

    const allowedTags = ['INPUT', 'TEXTAREA']
    if (allowedTags.includes(target.tagName)) {
      const inputType = (target as HTMLInputElement).type
      if (inputType === 'password') return false
      return true
    }

    return target.isContentEditable
  }

  private sendEventViaBeacon(eventType: string, data: any) {
    try {
      const payload = JSON.stringify({
        type: eventType,
        attempt_id: this.attemptId,
        exam_id: this.examId,
        data: {
          ...data,
          timestamp: new Date().toISOString()
        }
      })

      if (navigator.sendBeacon) {
        const blob = new Blob([payload], { type: 'application/json' })
        navigator.sendBeacon('/api/exams/anti-cheating/beacon/', blob)
      }
    } catch (e) {
      console.warn('Failed to send beacon:', e)
    }
  }

  private recordCheatingEvent(
    eventType: string,
    description: string,
    severity: 'low' | 'medium' | 'high' | 'critical',
    details?: Record<string, any>
  ) {
    const event: CheatingEvent = {
      eventType,
      description,
      severity,
      timestamp: new Date(),
      details
    }

    this.events.push(event)
    this.onCheatingDetected?.(event)

    console.warn('Anti-cheating event detected:', event)
  }

  private sendAntiCheatingEvent(eventType: string, details: any = {}) {
    if (!this.attemptId) return

    const success = this.sendToWebSocket('anti_cheating_event', {
      event_type: eventType,
      details: {
        ...details,
        timestamp: new Date().toISOString()
      }
    })

    if (!success) {
      this.pendingEvents.push({
        type: 'anti_cheating_event',
        data: {
          event_type: eventType,
          details: {
            ...details,
            timestamp: new Date().toISOString()
          }
        },
        timestamp: Date.now(),
        retryCount: 0
      })
      this.savePendingEvents()
    }
  }

  private sendToWebSocket(type: string, data: any): boolean {
    if (examMonitoringSocket.getConnectionStatus()) {
      examMonitoringSocket.send({
        type,
        data
      })
      return true
    }
    return false
  }

  private checkForceSubmitCondition(violationType: string) {
    if (this.isForceSubmitting) return

    const threshold = this.config.violationThreshold[violationType] || this.config.maxViolations

    let shouldForceSubmit = false
    let reason = ''

    if (violationType === 'tab_switch' && this.violationState.tabSwitchCount >= this.config.maxTabSwitches) {
      shouldForceSubmit = true
      reason = `切出页面次数超过限制(${this.config.maxTabSwitches}次)`
    } else if (this.violationState.totalViolations >= this.config.maxViolations) {
      shouldForceSubmit = true
      reason = `违规次数超过限制(${this.config.maxViolations}次)`
    }

    if (shouldForceSubmit) {
      this.isForceSubmitting = true

      ElMessage.error({
        message: `系统检测到违规行为：${reason}，考试将被强制提交`,
        duration: 0
      })

      setTimeout(() => {
        this.onForceSubmit?.()
      }, 3000)
    }
  }

  private async requestFaceVerification() {
    if (!this.config.enableFaceVerification || !this.isMonitoring) return

    try {
      await ElMessageBox.alert('请进行人脸验证以继续考试', '人脸验证', {
        confirmButtonText: '开始验证',
        type: 'info'
      })

      this.sendAntiCheatingEvent('face_verification', {
        is_verified: true,
        timestamp: new Date().toISOString()
      })

    } catch {
      this.recordCheatingEvent(
        'face_verify_fail',
        '人脸验证被取消或失败',
        'high'
      )

      this.sendAntiCheatingEvent('face_verification', {
        is_verified: false,
        timestamp: new Date().toISOString()
      })

      ElMessage.error('人脸验证失败，考试将被强制提交')

      setTimeout(() => {
        this.onForceSubmit?.()
      }, 2000)
    }
  }

  async enterFullscreen(): Promise<boolean> {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen()
        this.inFullscreen = true
        return true
      }
      return true
    } catch (error) {
      console.warn('Failed to enter fullscreen:', error)
      return false
    }
  }

  async exitFullscreen(): Promise<void> {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen()
      }
    } catch (error) {
      console.warn('Failed to exit fullscreen:', error)
    }
  }

  sendActivity(activityType: string, details: any = {}) {
    if (!this.attemptId || this.isForceSubmitting) return

    this.lastActivityTime = new Date()
    this.saveToStorage(STORAGE_KEYS.LAST_ACTIVITY, new Date().toISOString())

    const success = this.sendToWebSocket('activity', {
      activity_type: activityType,
      details: {
        ...details,
        timestamp: new Date().toISOString()
      }
    })

    if (!success) {
      this.pendingEvents.push({
        type: 'activity',
        data: {
          activity_type: activityType,
          details: {
            ...details,
            timestamp: new Date().toISOString()
          }
        },
        timestamp: Date.now(),
        retryCount: 0
      })
      this.savePendingEvents()
    }
  }

  sendAnswerUpdate(questionId: number, answerData: {
    answer_text?: string
    answer_choice?: string[]
    is_skipped?: boolean
    is_flagged?: boolean
    time_spent?: number
  }) {
    if (!this.attemptId || this.isForceSubmitting) return

    this.lastActivityTime = new Date()
    this.saveToStorage(STORAGE_KEYS.LAST_ACTIVITY, new Date().toISOString())

    const success = this.sendToWebSocket('answer_update', {
      question_id: questionId,
      ...answerData
    })

    if (!success) {
      this.pendingEvents.push({
        type: 'answer_update',
        data: {
          question_id: questionId,
          ...answerData,
          timestamp: new Date().toISOString()
        },
        timestamp: Date.now(),
        retryCount: 0
      })
      this.savePendingEvents()
    }
  }

  sendHeartbeat() {
    if (!this.attemptId || this.isForceSubmitting) return

    this.lastActivityTime = new Date()
    this.saveToStorage(STORAGE_KEYS.LAST_ACTIVITY, new Date().toISOString())

    this.sendToWebSocket('heartbeat', {
      timestamp: new Date().toISOString(),
      violation_state: this.violationState
    })
  }

  getTabSwitchCount(): number {
    return this.violationState.tabSwitchCount
  }

  getViolationState(): ViolationState {
    return { ...this.violationState }
  }

  getCheatingEvents(): CheatingEvent[] {
    return [...this.events]
  }

  isInFullscreen(): boolean {
    return this.inFullscreen
  }

  isMonitoringActive(): boolean {
    return this.isMonitoring
  }

  stop() {
    this.isMonitoring = false
    this.isInitialized = false

    this.stopIdleCheck()
    this.stopFaceVerification()
    this.stopPendingRetry()
    this.unbindEventListeners()
    this.exitFullscreen()

    this.retryPendingEvents()
    this.clearStorage()

    console.log('Exam anti-cheating stopped')
  }

  private tabSwitchCount: number = 0
}

export const examAntiCheating = new ExamAntiCheating()

export function useExamAntiCheating() {
  const isMonitoring = ref(false)
  const tabSwitchCount = ref(0)
  const cheatingEvents = ref<CheatingEvent[]>([])
  const inFullscreen = ref(true)
  const violationState = ref<ViolationState>({
    tabSwitchCount: 0,
    copyAttempts: 0,
    pasteAttempts: 0,
    rightClickAttempts: 0,
    fullscreenExits: 0,
    idleViolations: 0,
    totalViolations: 0
  })

  const startMonitoring = (attemptId: number, examId?: number, config?: Partial<AntiCheatingConfig>) => {
    examAntiCheating.init(attemptId, examId, config)
    isMonitoring.value = true
    tabSwitchCount.value = examAntiCheating.getTabSwitchCount()
    violationState.value = examAntiCheating.getViolationState()

    examAntiCheating.onCheatingDetected = (event) => {
      cheatingEvents.value.push(event)
      tabSwitchCount.value = examAntiCheating.getTabSwitchCount()
      violationState.value = examAntiCheating.getViolationState()
    }
  }

  const stopMonitoring = () => {
    examAntiCheating.stop()
    isMonitoring.value = false
  }

  onUnmounted(() => {
    if (isMonitoring.value) {
      examAntiCheating.stop()
    }
  })

  return {
    isMonitoring,
    tabSwitchCount,
    cheatingEvents,
    inFullscreen,
    violationState,
    startMonitoring,
    stopMonitoring,
    sendActivity: examAntiCheating.sendActivity.bind(examAntiCheating),
    sendAnswerUpdate: examAntiCheating.sendAnswerUpdate.bind(examAntiCheating),
    sendHeartbeat: examAntiCheating.sendHeartbeat.bind(examAntiCheating),
    enterFullscreen: examAntiCheating.enterFullscreen.bind(examAntiCheating),
    getViolationState: examAntiCheating.getViolationState.bind(examAntiCheating),
    isMonitoringActive: examAntiCheating.isMonitoringActive.bind(examAntiCheating)
  }
}

export type { AntiCheatingConfig, CheatingEvent, ViolationState }
