import { request } from './request'

export interface LearningSession {
  id: number
  student: any
  course: any
  lesson: any | null
  session_type: string
  start_time: string
  end_time: string | null
  duration: number | null
  effective_duration: number
  is_active: boolean
  device_info: string | null
  ip_address: string | null
  location: string | null
  interactions: any[]
  focus_intervals: any[]
  distraction_events: any[]
  focus_score: number | null
  efficiency_score: number | null
  created_at: string
}

export interface DailyLearningStats {
  id: number
  student: any
  date: string
  total_sessions: number
  total_duration: number
  effective_duration: number
  courses_visited: number
  lessons_completed: number
  assignments_submitted: number
  assignments_graded: number
  exams_taken: number
  exams_passed: number
  average_focus_score: number | null
  average_efficiency_score: number | null
  streak_days: number
  is_learning_day: boolean
  created_at: string
}

export interface CourseProgressStats {
  id: number
  student: any
  course: any
  enrollment: any
  overall_progress: number
  total_lessons: number
  completed_lessons: number
  in_progress_lessons: number
  total_video_duration: number
  watched_video_duration: number
  total_assignments: number
  submitted_assignments: number
  graded_assignments: number
  assignments_average_score: string | null
  total_exams: number
  taken_exams: number
  passed_exams: number
  exams_average_score: string | null
  first_access_at: string | null
  last_access_at: string | null
  total_study_time: number
  estimated_remaining_time: number
  learning_speed_score: number | null
  mastery_score: number | null
  predicted_completion_date: string | null
  created_at: string
}

export interface LearningBehavior {
  id: number
  student: any
  course: any
  lesson: any | null
  behavior_type: string
  details: any
  timestamp: string
  session_id: string | null
  created_at: string
}

export interface LearningAnalytics {
  id: number
  student: any
  course: any
  analysis_date: string
  overall_engagement_score: number | null
  video_watching_pattern: any
  video_completion_rate: number | null
  average_playback_speed: number | null
  seek_frequency: number | null
  assignment_submission_pattern: any
  assignment_on_time_rate: number | null
  assignment_avg_score: string | null
  exam_performance: any
  exam_avg_score: string | null
  exam_pass_rate: number | null
  learning_time_distribution: any
  peak_learning_hours: number[]
  weekly_learning_pattern: any
  focus_analysis: any
  average_focus_score: number | null
  distraction_events_count: number
  predictions: any
  predicted_final_score: string | null
  completion_probability: number | null
  dropout_risk: string | null
  strengths: string[]
  weaknesses: string[]
  recommendations: string[]
  created_at: string
}

export interface ClassAnalytics {
  id: number
  class_obj: any
  analysis_date: string
  total_students: number
  active_students: number
  at_risk_students: number
  average_attendance_rate: number | null
  average_progress: number | null
  assignment_submission_rate: number | null
  assignment_average_score: string | null
  exam_average_score: string | null
  exam_pass_rate: number | null
  weekly_activity_trend: any[]
  score_distribution: any
  progress_distribution: any
  top_performers: any[]
  struggling_students: any[]
  class_engagement_score: number | null
  learning_efficiency_index: number | null
  insights: any[]
  recommendations: any[]
  created_at: string
}

export const analyticsApi = {
  startSession(data: {
    course_id: number
    lesson_id?: number
    session_type?: string
  }): Promise<LearningSession> {
    return request.post('/analytics/learning-sessions/start/', data)
  },

  updateSession(sessionId: number, data: {
    focus_score?: number
    efficiency_score?: number
    interactions?: any[]
    focus_intervals?: any[]
    distraction_events?: any[]
  }): Promise<LearningSession> {
    return request.post(`/analytics/learning-sessions/${sessionId}/update_session/`, data)
  },

  endSession(sessionId: number): Promise<LearningSession> {
    return request.post(`/analytics/learning-sessions/${sessionId}/end/`)
  },

  getMyDailyStats(days: number = 30): Promise<DailyLearningStats[]> {
    return request.get('/analytics/daily-stats/my_stats/', { params: { days } })
  },

  getDailySummary(days: number = 30): Promise<{
    period: any
    summary: any
    average_per_learning_day: any
  }> {
    return request.get('/analytics/daily-stats/summary/', { params: { days } })
  },

  getMyCourseProgress(): Promise<CourseProgressStats[]> {
    return request.get('/analytics/course-progress/my_progress/')
  },

  getCourseProgressDetail(progressId: number): Promise<CourseProgressStats & { chapters: any[] }> {
    return request.get(`/analytics/course-progress/${progressId}/detailed/`)
  },

  recordBehavior(data: {
    course_id: number
    lesson_id?: number
    behavior_type: string
    details?: any
    session_id?: string
  }): Promise<any> {
    return request.post('/analytics/learning-behaviors/record/', data)
  },

  getBehaviorAnalysis(days: number = 14): Promise<any> {
    return request.get('/analytics/learning-behaviors/analysis/', { params: { days } })
  },

  getMyAnalytics(courseId?: number): Promise<LearningAnalytics> {
    const params = courseId ? { course_id: courseId } : {}
    return request.get('/analytics/learning-analytics/my_analytics/', { params })
  },

  getDashboard(): Promise<any> {
    return request.get('/analytics/learning-analytics/dashboard/')
  },

  getClassAnalyticsDetail(analyticsId: number): Promise<any> {
    return request.get(`/analytics/class-analytics/${analyticsId}/detailed/`)
  },

  getTeacherDashboard(): Promise<any> {
    return request.get('/analytics/class-analytics/teacher_dashboard/')
  },

  getLearningSessions(params?: {
    course?: number
    lesson?: number
    session_type?: string
    is_active?: boolean
  }): Promise<any> {
    return request.get('/analytics/learning-sessions/', { params })
  },

  getActiveSession(): Promise<LearningSession | null> {
    return request.get('/analytics/learning-sessions/', { params: { is_active: true } })
  }
}
