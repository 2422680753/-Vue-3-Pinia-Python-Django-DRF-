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
}

interface CheatingEvent {
  eventType: string
  description: string
  severity: 'low' | 'medium' | 'high'
  timestamp: Date
}

class ExamAntiCheating {
  private attemptId: number | null = null
  private config: AntiCheatingConfig = {
    maxTabSwitches: 5,
    maxIdleTime: 300,
    requireFullscreen: true,
    blockCopyPaste: true,
    blockRightClick: true,
    enableFaceVerification: false,
    verifyInterval: 300
  }
  
  private tabSwitchCount: number = 0
  private idleStartTime: Date | null = null
  private lastActivityTime: Date = new Date()
  private inFullscreen: boolean = true
  
  private events: CheatingEvent[] = []
  private isMonitoring: boolean = false
  
  private boundHandlers: {
    visibilityChange: () => void
    fullscreenChange: () => void
    copy: (e: Event) => void
    paste: (e: Event) => void
    cut: (e: Event) => void
    contextMenu: (e: Event) => void
    activity: () => void
    beforeUnload: (e: BeforeUnloadEvent) => string | undefined
  } | null = null
  
  private idleCheckInterval: number | null = null
  private faceVerifyInterval: number | null = null
  
  public onCheatingDetected: ((event: CheatingEvent) => void) | null = null
  public onForceSubmit: (() => void) | null = null

  init(attemptId: number, config?: Partial<AntiCheatingConfig>) {
    this.attemptId = attemptId
    this.config = { ...this.config, ...config }
    this.tabSwitchCount = 0
    this.idleStartTime = null
    this.lastActivityTime = new Date()
    this.inFullscreen = true
    this.events = []
    this.isMonitoring = true
    
    this.bindEventListeners()
    this.startIdleCheck()
    
    if (this.config.enableFaceVerification) {
      this.startFaceVerification()
    }
    
    this.enterFullscreen()
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
      beforeUnload: this.handleBeforeUnload.bind(this)
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
    window.addEventListener('keydown', this.boundHandlers.activity)
    window.addEventListener('click', this.boundHandlers.activity)
    window.addEventListener('scroll', this.boundHandlers.activity)
    
    window.addEventListener('beforeunload', this.boundHandlers.beforeUnload)
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
    window.removeEventListener('keydown', this.boundHandlers.activity)
    window.removeEventListener('click', this.boundHandlers.activity)
    window.removeEventListener('scroll', this.boundHandlers.activity)
    
    window.removeEventListener('beforeunload', this.boundHandlers.beforeUnload)
  }

  private startIdleCheck() {
    this.idleCheckInterval = window.setInterval(() => {
      const now = new Date()
      const idleTime = (now.getTime() - this.lastActivityTime.getTime()) / 1000
      
      if (idleTime > this.config.maxIdleTime) {
        this.recordCheatingEvent(
          'idle_too_long',
          `长时间空闲，空闲时长: ${idleTime.toFixed(1)}秒`,
          'medium'
        )
        
        this.sendAntiCheatingEvent('idle_too_long', {
          idle_duration: idleTime,
          max_allowed: this.config.maxIdleTime
        })
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

  private handleVisibilityChange() {
    if (!this.isMonitoring) return
    
    if (document.hidden) {
      this.tabSwitchCount++
      this.idleStartTime = new Date()
      
      this.recordCheatingEvent(
        'tab_switch',
        `切出页面，当前切出次数: ${this.tabSwitchCount}`,
        this.tabSwitchCount > this.config.maxTabSwitches ? 'high' : 'low'
      )
      
      this.sendAntiCheatingEvent('tab_leave', {
        count: this.tabSwitchCount
      })
      
      if (this.tabSwitchCount > this.config.maxTabSwitches) {
        ElMessage.error({
          message: `切出页面次数超过限制(${this.config.maxTabSwitches}次)，考试将被强制提交`,
          duration: 0
        })
        
        setTimeout(() => {
          this.onForceSubmit?.()
        }, 3000)
      }
    } else {
      this.lastActivityTime = new Date()
      this.sendAntiCheatingEvent('tab_return', {
        count: this.tabSwitchCount
      })
    }
  }

  private handleFullscreenChange() {
    if (!this.isMonitoring) return
    
    const isFullscreen = !!document.fullscreenElement
    
    if (!isFullscreen && this.config.requireFullscreen) {
      this.inFullscreen = false
      
      this.recordCheatingEvent(
        'fullscreen_exit',
        '考试期间退出全屏模式',
        'medium'
      )
      
      this.sendAntiCheatingEvent('fullscreen_exit', {})
      
      ElMessage.warning('请保持全屏模式进行考试')
      
      setTimeout(() => {
        if (!document.fullscreenElement) {
          this.enterFullscreen()
        }
      }, 1000)
    } else {
      this.inFullscreen = true
      this.sendAntiCheatingEvent('fullscreen_enter', {})
    }
  }

  private handleCopy(e: Event) {
    if (!this.isMonitoring) return
    
    e.preventDefault()
    
    this.recordCheatingEvent(
      'copy_attempt',
      '考试期间尝试复制内容',
      'low'
    )
    
    this.sendAntiCheatingEvent('copy_attempt', {
      timestamp: new Date().toISOString()
    })
    
    ElMessage.warning('考试期间禁止复制')
  }

  private handlePaste(e: Event) {
    if (!this.isMonitoring) return
    
    e.preventDefault()
    
    this.recordCheatingEvent(
      'paste_attempt',
      '考试期间尝试粘贴内容',
      'low'
    )
    
    this.sendAntiCheatingEvent('paste_attempt', {
      timestamp: new Date().toISOString()
    })
    
    ElMessage.warning('考试期间禁止粘贴')
  }

  private handleCut(e: Event) {
    if (!this.isMonitoring) return
    
    e.preventDefault()
    
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

  private handleContextMenu(e: Event) {
    if (!this.isMonitoring) return
    
    e.preventDefault()
    
    this.sendAntiCheatingEvent('right_click', {
      timestamp: new Date().toISOString()
    })
  }

  private handleActivity() {
    if (!this.isMonitoring) return
    
    this.lastActivityTime = new Date()
    this.idleStartTime = null
  }

  private handleBeforeUnload(e: BeforeUnloadEvent): string | undefined {
    if (!this.isMonitoring) return
    
    const message = '考试进行中，确定要离开吗？离开后考试将被提交！'
    e.preventDefault()
    e.returnValue = message
    return message
  }

  private recordCheatingEvent(eventType: string, description: string, severity: 'low' | 'medium' | 'high') {
    const event: CheatingEvent = {
      eventType,
      description,
      severity,
      timestamp: new Date()
    }
    
    this.events.push(event)
    this.onCheatingDetected?.(event)
    
    console.warn('Anti-cheating event detected:', event)
  }

  private sendAntiCheatingEvent(eventType: string, details: any = {}) {
    if (!this.attemptId) return
    
    examMonitoringSocket.send({
      type: 'anti_cheating_event',
      data: {
        event_type: eventType,
        details: {
          ...details,
          timestamp: new Date().toISOString()
        }
      }
    })
  }

  private async requestFaceVerification() {
    if (!this.config.enableFaceVerification) return
    
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
        'face_verify_cancelled',
        '人脸验证被取消',
        'high'
      )
      
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
      console.error('Failed to enter fullscreen:', error)
      return false
    }
  }

  async exitFullscreen(): Promise<void> {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen()
      }
    } catch (error) {
      console.error('Failed to exit fullscreen:', error)
    }
  }

  sendActivity(activityType: string, details: any = {}) {
    if (!this.attemptId) return
    
    examMonitoringSocket.send({
      type: 'activity',
      data: {
        activity_type: activityType,
        details: {
          ...details,
          timestamp: new Date().toISOString()
        }
      }
    })
  }

  sendAnswerUpdate(questionId: number, answerData: {
    answer_text?: string
    answer_choice?: string[]
    is_skipped?: boolean
    is_flagged?: boolean
    time_spent?: number
  }) {
    if (!this.attemptId) return
    
    examMonitoringSocket.send({
      type: 'answer_update',
      data: {
        question_id: questionId,
        ...answerData
      }
    })
  }

  getTabSwitchCount(): number {
    return this.tabSwitchCount
  }

  getCheatingEvents(): CheatingEvent[] {
    return [...this.events]
  }

  isInFullscreen(): boolean {
    return this.inFullscreen
  }

  stop() {
    this.isMonitoring = false
    this.stopIdleCheck()
    this.stopFaceVerification()
    this.unbindEventListeners()
    this.exitFullscreen()
  }
}

export const examAntiCheating = new ExamAntiCheating()

export function useExamAntiCheating() {
  const isMonitoring = ref(false)
  const tabSwitchCount = ref(0)
  const cheatingEvents = ref<CheatingEvent[]>([])
  const inFullscreen = ref(true)

  const startMonitoring = (attemptId: number, config?: Partial<AntiCheatingConfig>) => {
    examAntiCheating.init(attemptId, config)
    isMonitoring.value = true
    tabSwitchCount.value = examAntiCheating.getTabSwitchCount()
    
    examAntiCheating.onCheatingDetected = (event) => {
      cheatingEvents.value.push(event)
      tabSwitchCount.value = examAntiCheating.getTabSwitchCount()
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
    startMonitoring,
    stopMonitoring,
    sendActivity: examAntiCheating.sendActivity.bind(examAntiCheating),
    sendAnswerUpdate: examAntiCheating.sendAnswerUpdate.bind(examAntiCheating),
    enterFullscreen: examAntiCheating.enterFullscreen.bind(examAntiCheating)
  }
}
