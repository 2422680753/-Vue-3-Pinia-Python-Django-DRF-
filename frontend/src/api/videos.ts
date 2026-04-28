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
  video: number
  user: number
  progress: number
  current_time: number
  duration: number
  is_completed: boolean
  last_watched_at: string
  watch_count: number
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
    return request.get('/videos/videos/', { params: { lesson: lessonId } })
  },

  getVideoDetail(videoId: number): Promise<Video> {
    return request.get(`/videos/videos/${videoId}/`)
  },

  getVideoProgress(videoId: number): Promise<VideoProgress> {
    return request.get(`/videos/progresses/by-video/?video_id=${videoId}`)
  },

  updateProgress(data: {
    video_id: number
    current_time: number
    duration: number
    is_playing?: boolean
    speed?: number
  }): Promise<any> {
    return request.post('/videos/progresses/update/', data)
  },

  completeVideo(videoId: number): Promise<any> {
    return request.post(`/videos/progresses/complete/`, { video_id: videoId })
  },

  getVideoSubtitles(videoId: number): Promise<Subtitle[]> {
    return request.get('/videos/subtitles/', { params: { video: videoId, is_active: true } })
  },

  recordHeartbeat(data: {
    video_id: number
    current_time: number
    duration: number
    is_playing: boolean
  }): Promise<any> {
    return request.post('/videos/progresses/heartbeat/', data)
  }
}
