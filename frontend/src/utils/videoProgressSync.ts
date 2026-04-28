import { Ref, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { videoApi, type VideoProgress } from '@/api/videos'
import { videoProgressSocket } from './websocket'

interface ProgressState {
  lessonId: number | null
  currentTime: number
  totalDuration: number
  progress: number
  version: number
  isCompleted: boolean
}

interface SyncRequest {
  requestId: string
  lessonId: number
  currentTime: number
  totalDuration: number
  timestamp: number
  isPlaying: boolean
}

interface LocalProgress {
  lessonId: number
  currentTime: number
  totalDuration: number
  progress: number
  version: number
  isCompleted: boolean
  lastSyncAt: number
  sessionId?: string
}

interface SyncConfig {
  debounceInterval: number
  maxInterval: number
  maxRetries: number
  retryDelay: number
  syncOnVisibilityChange: boolean
}

const DEFAULT_CONFIG: SyncConfig = {
  debounceInterval: 3000,
  maxInterval: 15000,
  maxRetries: 3,
  retryDelay: 2000,
  syncOnVisibilityChange: true
}

class VideoProgressSyncManager {
  private config: SyncConfig = DEFAULT_CONFIG
  private lessonId: number | null = null
  private sessionId: string | null = null
  
  private currentTime: number = 0
  private totalDuration: number = 0
  private progress: number = 0
  private version: number = 1
  private isCompleted: boolean = false
  
  private debounceTimer: number | null = null
  private intervalTimer: number | null = null
  private lastSyncTime: number = 0
  
  private pendingRequests: Map<string, SyncRequest> = new Map()
  private failedRequests: SyncRequest[] = []
  private retryTimer: number | null = null
  
  private isPlaying: boolean = false
  private isSeeking: boolean = false
  private seekFrom: number | null = null
  private seekTo: number | null = null
  
  private isInitialized: boolean = false
  private onProgressUpdate: ((state: ProgressState) => void) | null = null
  private onConflict: ((conflict: any) => void) | null = null
  private onComplete: (() => void) | null = null
  
  private visibilityChangeListener: (() => void) | null = null
  private beforeUnloadListener: ((e: BeforeUnloadEvent) => void) | null = null
  
  constructor(config?: Partial<SyncConfig>) {
    if (config) {
      this.config = { ...DEFAULT_CONFIG, ...config }
    }
  }

  async init(lessonId: number, onProgressUpdate?: (state: ProgressState) => void, 
             onConflict?: (conflict: any) => void,
             onComplete?: () => void): Promise<void> {
    this.lessonId = lessonId
    this.isInitialized = true
    this.onProgressUpdate = onProgressUpdate || null
    this.onConflict = onConflict || null
    this.onComplete = onComplete || null
    
    const localProgress = this.getLocalProgress(lessonId)
    if (localProgress) {
      this.currentTime = localProgress.currentTime
      this.totalDuration = localProgress.totalDuration
      this.progress = localProgress.progress
      this.version = localProgress.version
      this.isCompleted = localProgress.isCompleted
      this.sessionId = localProgress.sessionId || null
    }
    
    let serverProgress: VideoProgress | null = null
    try {
      serverProgress = await videoApi.getVideoProgress(lessonId)
      
      if (serverProgress && !('exists' in serverProgress && serverProgress.exists === false)) {
        const serverTime = serverProgress.current_time || 0
        const serverProgressVal = serverProgress.progress || 0
        const serverVersion = serverProgress.version || 1
        
        if (this.isCompleted) {
          this.notifyUpdate()
          return
        }
        
        if (serverVersion > this.version) {
          this.currentTime = serverTime
          this.progress = serverProgressVal
          this.version = serverVersion
          this.isCompleted = serverProgress.is_completed || false
          this.totalDuration = serverProgress.total_duration || this.totalDuration
          this.saveLocalProgress()
          
          ElMessage({
            message: '已同步其他设备的播放进度',
            type: 'info',
            duration: 3000
          })
        } else if (localProgress && this.currentTime > serverTime + 60) {
          if (this.onConflict) {
            this.onConflict({
              type: 'time_conflict',
              localTime: this.currentTime,
              serverTime: serverTime,
              localVersion: this.version,
              serverVersion: serverVersion
            })
          }
        }
      }
    } catch (error: any) {
      console.warn('Failed to fetch server progress:', error)
      
      if (error.response?.data?.exists === false) {
        console.log('No progress record found, will create new one')
      }
    }
    
    try {
      const sessionResponse = await videoApi.startSession(lessonId)
      this.sessionId = sessionResponse.session_id
      this.saveLocalProgress()
      
      if (sessionResponse.active_sessions_terminated > 0) {
        ElMessage({
          message: `已终止 ${sessionResponse.active_sessions_terminated} 个其他设备的播放会话`,
          type: 'warning',
          duration: 3000
        })
      }
    } catch (error) {
      console.warn('Failed to start session:', error)
    }
    
    this.startTimers()
    this.setupPageListeners()
    
    this.notifyUpdate()
  }

  private async resolveConflict(local: { time: number; version: number }, 
                                   server: { time: number; version: number }): Promise<boolean> {
    if (server.version > local.version) {
      return false
    }
    
    if (local.time > server.time) {
      return true
    }
    
    return false
  }

  setProgress(time: number, duration: number): void {
    if (!this.isInitialized || !this.lessonId) return
    
    const previousTime = this.currentTime
    
    this.currentTime = time
    if (duration > 0) {
      this.totalDuration = duration
    }
    
    if (this.totalDuration > 0) {
      this.progress = Math.min(time / this.totalDuration, 1.0)
    }
    
    if (!this.isCompleted && this.progress >= 0.9) {
      this.isCompleted = true
      if (this.onComplete) {
        this.onComplete()
      }
    }
    
    this.saveLocalProgress()
    this.scheduleSync()
    this.notifyUpdate()
  }

  setPlaying(isPlaying: boolean): void {
    this.isPlaying = isPlaying
    
    if (isPlaying) {
      this.scheduleSync()
    } else {
      this.flushSync()
    }
  }

  startSeek(fromTime: number): void {
    this.isSeeking = true
    this.seekFrom = fromTime
  }

  endSeek(toTime: number): void {
    this.isSeeking = false
    this.seekTo = toTime
    
    this.flushSync(true, this.seekFrom, this.seekTo)
    
    this.seekFrom = null
    this.seekTo = null
  }

  private scheduleSync(): void {
    if (!this.isPlaying && this.progress < 0.9) {
      return
    }
    
    const now = Date.now()
    const timeSinceLastSync = now - this.lastSyncTime
    
    if (timeSinceLastSync >= this.config.maxInterval) {
      this.flushSync()
      return
    }
    
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer)
    }
    
    this.debounceTimer = window.setTimeout(() => {
      this.flushSync()
    }, this.config.debounceInterval)
  }

  private async flushSync(isSeeked: boolean = false, 
                           seekFrom: number | null = null, 
                           seekTo: number | null = null): Promise<void> {
    if (!this.lessonId) return
    
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer)
      this.debounceTimer = null
    }
    
    const requestId = this.generateRequestId()
    const syncData = {
      lesson_id: this.lessonId,
      current_time: this.currentTime,
      total_duration: this.totalDuration,
      playback_rate: 1.0,
      is_seeked: isSeeked,
      seek_from: seekFrom,
      seek_to: seekTo,
      is_playing: this.isPlaying,
      request_id: requestId,
      client_version: this.version,
      session_id: this.sessionId || undefined
    }
    
    this.pendingRequests.set(requestId, {
      requestId,
      lessonId: this.lessonId,
      currentTime: this.currentTime,
      totalDuration: this.totalDuration,
      timestamp: Date.now(),
      isPlaying: this.isPlaying
    })
    
    try {
      const response = await videoApi.syncProgress(syncData)
      
      this.lastSyncTime = Date.now()
      this.pendingRequests.delete(requestId)
      
      if (response.conflict) {
        console.warn('Progress conflict detected:', response.conflict)
        
        const { type, resolution } = response.conflict
        
        if (resolution.action === 'sync_required' && resolution.server_version) {
          this.version = resolution.server_version
          this.saveLocalProgress()
          
          if (this.onConflict) {
            this.onConflict(response.conflict)
          }
        }
        
        if (resolution.action === 'reject') {
          ElMessage.warning({
            message: '检测到进度冲突，已使用服务器最新进度',
            duration: 4000
          })
          
          if (resolution.server_time !== undefined && resolution.server_time > this.currentTime) {
            this.currentTime = resolution.server_time
            if (this.totalDuration > 0) {
              this.progress = resolution.server_time / this.totalDuration
            }
            this.notifyUpdate()
          }
        }
      }
      
      if (response.version && response.version > this.version) {
        this.version = response.version
        this.saveLocalProgress()
      }
      
      if (response.is_completed && !this.isCompleted) {
        this.isCompleted = true
        this.notifyUpdate()
        
        if (this.onComplete) {
          this.onComplete()
        }
      }
      
      if (videoProgressSocket.getConnectionStatus() && this.sessionId) {
        videoProgressSocket.send({
          type: 'progress',
          data: {
            video_id: this.lessonId,
            progress: this.progress,
            current_time: this.currentTime,
            duration: this.totalDuration,
            is_playing: this.isPlaying,
            session_id: this.sessionId
          }
        })
      }
      
    } catch (error: any) {
      console.error('Progress sync failed:', error)
      
      const request = this.pendingRequests.get(requestId)
      if (request) {
        this.pendingRequests.delete(requestId)
        this.failedRequests.push(request)
      }
      
      this.scheduleRetry()
    }
  }

  private scheduleRetry(): void {
    if (this.retryTimer) {
      return
    }
    
    this.retryTimer = window.setInterval(async () => {
      if (this.failedRequests.length === 0) {
        if (this.retryTimer) {
          clearInterval(this.retryTimer)
          this.retryTimer = null
        }
        return
      }
      
      const request = this.failedRequests.shift()
      if (!request) return
      
      try {
        await videoApi.syncProgress({
          lesson_id: request.lessonId,
          current_time: request.currentTime,
          total_duration: request.totalDuration,
          is_playing: request.isPlaying,
          request_id: request.requestId,
          session_id: this.sessionId || undefined
        })
        
        this.lastSyncTime = Date.now()
        
      } catch (error) {
        console.error('Retry sync failed:', error)
        this.failedRequests.push(request)
        
        if (this.failedRequests.length > this.config.maxRetries * 3) {
          this.failedRequests = this.failedRequests.slice(-10)
        }
      }
    }, this.config.retryDelay)
  }

  private startTimers(): void {
    this.intervalTimer = window.setInterval(() => {
      if (this.isPlaying || this.failedRequests.length > 0) {
        this.flushSync()
      }
    }, this.config.maxInterval)
  }

  private setupPageListeners(): void {
    if (!this.config.syncOnVisibilityChange) return
    
    this.visibilityChangeListener = async () => {
      if (document.visibilityState === 'hidden') {
        this.flushSync()
        
        if (this.sessionId) {
          try {
            await videoApi.endSession(this.sessionId, this.currentTime)
          } catch (error) {
            console.warn('Failed to end session on hide:', error)
          }
        }
      } else if (document.visibilityState === 'visible' && this.lessonId) {
        if (!this.sessionId) {
          try {
            const response = await videoApi.startSession(this.lessonId)
            this.sessionId = response.session_id
            this.saveLocalProgress()
          } catch (error) {
            console.warn('Failed to restart session:', error)
          }
        }
        
        try {
          const serverProgress = await videoApi.getVideoProgress(this.lessonId)
          if (serverProgress && !('exists' in serverProgress && serverProgress.exists === false)) {
            if (serverProgress.version > this.version) {
              this.currentTime = serverProgress.current_time || 0
              this.progress = serverProgress.progress || 0
              this.version = serverProgress.version || 1
              this.totalDuration = serverProgress.total_duration || this.totalDuration
              this.saveLocalProgress()
              this.notifyUpdate()
              
              ElMessage.info('已同步最新播放进度')
            }
          }
        } catch (error) {
          console.warn('Failed to sync on visible:', error)
        }
      }
    }
    
    this.beforeUnloadListener = (e: BeforeUnloadEvent) => {
      if (this.sessionId) {
        this.flushSync()
        
        navigator.sendBeacon(
          '/api/videos/progresses/session-end/',
          JSON.stringify({
            session_id: this.sessionId,
            final_time: this.currentTime
          })
        )
      }
      
      e.preventDefault()
      e.returnValue = '您的播放进度将被保存'
      return e.returnValue
    }
    
    document.addEventListener('visibilitychange', this.visibilityChangeListener)
    window.addEventListener('beforeunload', this.beforeUnloadListener)
  }

  private saveLocalProgress(): void {
    if (!this.lessonId) return
    
    const progress: LocalProgress = {
      lessonId: this.lessonId,
      currentTime: this.currentTime,
      totalDuration: this.totalDuration,
      progress: this.progress,
      version: this.version,
      isCompleted: this.isCompleted,
      lastSyncAt: Date.now()
    }
    
    if (this.sessionId) {
      progress.sessionId = this.sessionId
    }
    
    try {
      const key = `video_progress_${this.lessonId}`
      localStorage.setItem(key, JSON.stringify(progress))
      
      const allKeys = Object.keys(localStorage).filter(k => k.startsWith('video_progress_'))
      if (allKeys.length > 50) {
        const oldestKeys = allKeys
          .map(key => {
            try {
              const data = JSON.parse(localStorage.getItem(key) || '{}')
              return { key, lastSyncAt: data.lastSyncAt || 0 }
            } catch {
              return { key, lastSyncAt: 0 }
            }
          })
          .sort((a, b) => a.lastSyncAt - b.lastSyncAt)
          .slice(0, 20)
        
        oldestKeys.forEach(({ key }) => localStorage.removeItem(key))
      }
    } catch (error) {
      console.warn('Failed to save local progress:', error)
    }
  }

  getLocalProgress(lessonId: number): LocalProgress | null {
    try {
      const key = `video_progress_${lessonId}`
      const data = localStorage.getItem(key)
      if (!data) return null
      
      return JSON.parse(data)
    } catch (error) {
      console.warn('Failed to load local progress:', error)
      return null
    }
  }

  clearLocalProgress(lessonId?: number): void {
    if (lessonId) {
      localStorage.removeItem(`video_progress_${lessonId}`)
    } else {
      const keys = Object.keys(localStorage).filter(k => k.startsWith('video_progress_'))
      keys.forEach(key => localStorage.removeItem(key))
    }
  }

  private generateRequestId(): string {
    return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  private notifyUpdate(): void {
    if (this.onProgressUpdate) {
      this.onProgressUpdate({
        lessonId: this.lessonId,
        currentTime: this.currentTime,
        totalDuration: this.totalDuration,
        progress: this.progress,
        version: this.version,
        isCompleted: this.isCompleted
      })
    }
  }

  async complete(): Promise<void> {
    if (!this.lessonId) return
    
    this.isCompleted = true
    this.progress = 1.0
    if (this.totalDuration > 0) {
      this.currentTime = this.totalDuration
    }
    
    this.saveLocalProgress()
    
    try {
      await videoApi.completeVideo(this.lessonId)
    } catch (error) {
      console.error('Failed to mark as complete:', error)
    }
    
    this.flushSync()
  }

  async destroy(): Promise<void> {
    this.flushSync()
    
    if (this.sessionId) {
      try {
        await videoApi.endSession(this.sessionId, this.currentTime)
      } catch (error) {
        console.warn('Failed to end session:', error)
      }
    }
    
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer)
      this.debounceTimer = null
    }
    
    if (this.intervalTimer) {
      clearInterval(this.intervalTimer)
      this.intervalTimer = null
    }
    
    if (this.retryTimer) {
      clearInterval(this.retryTimer)
      this.retryTimer = null
    }
    
    if (this.visibilityChangeListener) {
      document.removeEventListener('visibilitychange', this.visibilityChangeListener)
      this.visibilityChangeListener = null
    }
    
    if (this.beforeUnloadListener) {
      window.removeEventListener('beforeunload', this.beforeUnloadListener)
      this.beforeUnloadListener = null
    }
    
    videoProgressSocket.disconnect()
    
    this.isInitialized = false
    this.onProgressUpdate = null
    this.onConflict = null
    this.onComplete = null
  }

  getState(): ProgressState {
    return {
      lessonId: this.lessonId,
      currentTime: this.currentTime,
      totalDuration: this.totalDuration,
      progress: this.progress,
      version: this.version,
      isCompleted: this.isCompleted
    }
  }
}

let globalSyncManager: VideoProgressSyncManager | null = null

export function useVideoProgressSync(config?: Partial<SyncConfig>) {
  if (!globalSyncManager) {
    globalSyncManager = new VideoProgressSyncManager(config)
  }
  
  return {
    syncManager: globalSyncManager,
    init: (lessonId: number, onUpdate?: (state: ProgressState) => void, 
          onConflict?: (conflict: any) => void,
          onComplete?: () => void) => 
      globalSyncManager!.init(lessonId, onUpdate, onConflict, onComplete),
    setProgress: (time: number, duration: number) => 
      globalSyncManager!.setProgress(time, duration),
    setPlaying: (isPlaying: boolean) => 
      globalSyncManager!.setPlaying(isPlaying),
    startSeek: (fromTime: number) => 
      globalSyncManager!.startSeek(fromTime),
    endSeek: (toTime: number) => 
      globalSyncManager!.endSeek(toTime),
    complete: () => 
      globalSyncManager!.complete(),
    destroy: () => 
      globalSyncManager!.destroy(),
    getState: () => 
      globalSyncManager!.getState(),
    getLocalProgress: (lessonId: number) => 
      globalSyncManager!.getLocalProgress(lessonId)
  }
}

export function createVideoProgressSync(config?: Partial<SyncConfig>) {
  return new VideoProgressSyncManager(config)
}

export type { ProgressState, LocalProgress, SyncConfig }
export default VideoProgressSyncManager
