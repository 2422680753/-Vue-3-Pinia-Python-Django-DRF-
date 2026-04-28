import { request } from './request'

export interface Video {
  id: number
  title: string
  description: string
  duration: number
  video_file: string
  hls_url: string | null
  thumbnail: string | null
  resolution: string
  bitrate: number
  video_type: string
  lesson: number
  is_active: boolean
  view_count: number
  created_at: string
}

export interface VideoProgress {
  id: number
  lesson: number
  lesson_id: number
  lesson_title: string
  course_id: number
  course_title: string
  chapter_id: number
  current_time: number
  total_duration: number
  play_count: number
  watch_duration: number
  progress: number
  is_completed: boolean
  completed_at: string | null
  last_watched_at: string
  created_at: string
  version: number
  last_update_time: string
  last_update_client: string | null
  last_update_ip: string | null
}

export interface VideoProgressSyncResponse extends VideoProgress {
  conflict?: {
    type: string
    resolution: {
      action: string
      reason?: string
      server_version?: number
      client_version?: number
      server_time?: number
      client_time?: number
      allowed_threshold?: number
    }
  }
  is_idempotent?: boolean
  server_time?: string
}

export interface StartSessionResponse {
  session_id: string
  start_time: string
  current_time: number
  progress: number
  is_completed: boolean
  version: number
  total_duration: number
  active_sessions_terminated: number
}

export interface EndSessionResponse {
  session_id: string
  status: string
  end_time: string
  total_seconds: number
  effective_seconds: number
  current_progress: {
    current_time: number
    progress: number
  }
}

export interface VideoWatchSession {
  id: number
  video_progress: number
  session_id: string
  start_time: string
  end_time: string | null
  initial_time: number
  final_time: number | null
  total_seconds: number
  effective_seconds: number
  is_active: boolean
  last_heartbeat: string
  ip_address: string | null
  device_info: string | null
  created_at: string
}

export interface VideoProgressConflict {
  id: number
  video_progress: number
  conflict_type: string
  conflict_type_display: string
  server_state: {
    current_time: number
    progress: number
    version: number
    last_update_time: string
  }
  client_state: {
    current_time: number
    progress: number
    version: number | null
    request_id: string | null
    session_id: string | null
  }
  resolution: {
    action: string
    [key: string]: any
  } | null
  is_resolved: boolean
  session_id: string | null
  ip_address: string | null
  device_info: string | null
  created_at: string
  resolved_at: string | null
}

export interface Subtitle {
  id: number
  video: number
  language: string
  label: string
  subtitle_file: string
  is_active: boolean
}

export const videoApi = {
  getVideoByLesson(lessonId: number): Promise<Video[]> {
    return request.get('/videos/sources/', { params: { lesson: lessonId } })
  },

  getVideoDetail(videoId: number): Promise<Video> {
    return request.get(`/videos/sources/${videoId}/`)
  },

  getVideoProgress(lessonId: number): Promise<VideoProgress> {
    return request.get(`/videos/progresses/by-lesson/${lessonId}/`)
  },

  syncProgress(data: {
    lesson_id: number
    current_time: number
    total_duration: number
    playback_rate?: number
    is_seeked?: boolean
    seek_from?: number | null
    seek_to?: number | null
    is_playing?: boolean
    request_id?: string
    client_version?: number
    session_id?: string
  }): Promise<VideoProgressSyncResponse> {
    return request.post('/videos/progresses/sync/', data)
  },

  batchSyncProgress(data: {
    items: Array<{
      lesson_id: number
      current_time: number
      total_duration: number
      playback_rate?: number
      is_seeked?: boolean
      seek_from?: number | null
      seek_to?: number | null
      is_playing?: boolean
      request_id?: string
      client_version?: number
      session_id?: string
    }>
    batch_id?: string
  }): Promise<{
    results: Array<{
      lesson_id: number
      data?: VideoProgressSyncResponse
      error?: string
      success: boolean
    }>
  }> {
    return request.post('/videos/progresses/batch-sync/', data)
  },

  startSession(lessonId: number): Promise<StartSessionResponse> {
    return request.post('/videos/progresses/session-start/', { lesson_id: lessonId })
  },

  sessionHeartbeat(sessionId: string): Promise<{
    session_id: string
    status: string
    last_heartbeat: string
    server_time: string
  }> {
    return request.post('/videos/progresses/session-heartbeat/', { session_id: sessionId })
  },

  endSession(sessionId: string, finalTime?: number): Promise<EndSessionResponse> {
    return request.post('/videos/progresses/session-end/', {
      session_id: sessionId,
      final_time: finalTime
    })
  },

  completeVideo(lessonId: number): Promise<VideoProgress> {
    return request.post('/videos/progresses/complete/', { lesson_id: lessonId })
  },

  getVideoSubtitles(lessonId: number): Promise<Subtitle[]> {
    return request.get('/videos/subtitles/', { params: { lesson: lessonId, is_active: true } })
  },

  getMyProgressStats(): Promise<{
    total_watch_time_seconds: number
    total_lessons: number
    completed_lessons: number
    completion_rate: number
    weekly_stats: Array<{
      date: string
      total_seconds: number
      session_count: number
    }>
  }> {
    return request.get('/videos/progresses/stats/')
  },

  getRecentProgresses(): Promise<VideoProgress[]> {
    return request.get('/videos/progresses/recent/')
  },

  getProgressConflicts(lessonId?: number): Promise<VideoProgressConflict[]> {
    const params = lessonId ? { video_progress__lesson: lessonId } : {}
    return request.get('/videos/conflicts/', { params })
  },

  updateProgress(data: {
    video_id: number
    current_time: number
    duration: number
    is_playing?: boolean
    speed?: number
  }): Promise<any> {
    return this.syncProgress({
      lesson_id: data.video_id,
      current_time: data.current_time,
      total_duration: data.duration,
      is_playing: data.is_playing,
      playback_rate: data.speed
    })
  },

  recordHeartbeat(data: {
    video_id: number
    current_time: number
    duration: number
    is_playing: boolean
  }): Promise<any> {
    return this.syncProgress({
      lesson_id: data.video_id,
      current_time: data.current_time,
      total_duration: data.duration,
      is_playing: data.is_playing
    })
  }
}
