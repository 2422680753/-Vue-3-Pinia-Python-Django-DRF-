import { request } from './request'

export interface Exam {
  id: number
  course: number
  teacher: any
  title: string
  description: string
  exam_type: string
  total_score: number
  pass_score: number
  total_questions: number
  duration: number
  allow_enter_before: number
  start_time: string
  end_time: string
  allow_late_enter: boolean
  late_enter_limit: number | null
  status: string
  show_score_immediately: boolean
  show_answers_after_exam: boolean
  show_analysis: boolean
  max_attempts: number
  auto_submit_on_timeout: boolean
  is_shuffle_questions: boolean
  is_shuffle_options: boolean
  enable_anti_cheating: boolean
  max_tab_switches: number
  max_idle_time: number
  require_fullscreen: boolean
  block_copy_paste: boolean
  block_right_click: boolean
  enable_face_verification: boolean
  verify_interval: number
  published_at: string | null
  my_attempt_status: string
  my_attempt_score: string | null
}

export interface ExamQuestion {
  id: number
  question_text: string
  question_type: string
  options: any[]
  question_order: number
  score: number
  correct_answer?: any
  explanation?: string
}

export interface ExamAttempt {
  id: number
  exam: Exam
  student: any
  attempt_number: number
  start_time: string
  submit_time: string | null
  end_time: string | null
  time_spent: number
  total_score: number | null
  score_percentage: number | null
  is_passed: boolean | null
  correct_count: number | null
  incorrect_count: number | null
  unanswered_count: number | null
  status: string
  is_cheating_detected: boolean
  cheating_reason: string | null
  submitted_manually: boolean
  auto_submit_reason: string | null
  ip_address: string
  device_info: string
  created_at: string
}

export interface ExamAnswer {
  id: number
  attempt: number
  question: number
  answer_text: string
  answer_choice: string[]
  is_answered: boolean
  is_skipped: boolean
  is_flagged: boolean
  is_correct: boolean | null
  score: number | null
  time_spent: number | null
}

export interface CheatingRecord {
  id: number
  attempt: number
  cheating_type: string
  description: string
  severity: string
  evidence: any
  action_taken: string | null
  is_verified: boolean
  verified_by: any | null
  verified_at: string | null
  created_at: string
}

export const examApi = {
  getMyExams(): Promise<{
    upcoming: Exam[]
    ongoing: Exam[]
    completed: Exam[]
  }> {
    return request.get('/exams/exams/my_exams/')
  },

  getExamDetail(id: number): Promise<Exam> {
    return request.get(`/exams/exams/${id}/`)
  },

  getExamAttempts(examId: number, params?: { status?: string }): Promise<any> {
    return request.get(`/exams/exams/${examId}/attempts/`, { params })
  },

  startExam(examId: number, data?: { password?: string }): Promise<ExamAttempt> {
    return request.post(`/exams/exams/${examId}/start/`, data || {})
  },

  submitAttempt(attemptId: number): Promise<ExamAttempt> {
    return request.post(`/exams/attempts/${attemptId}/submit/`)
  },

  getAttemptDetail(attemptId: number): Promise<ExamAttempt> {
    return request.get(`/exams/attempts/${attemptId}/`)
  },

  getAttemptAnswers(attemptId: number): Promise<ExamAnswer[]> {
    return request.get(`/exams/attempts/${attemptId}/answers/`)
  },

  getExamStats(examId: number): Promise<any> {
    return request.get(`/exams/exams/${examId}/stats/`)
  },

  getQuestionBank(params?: {
    course?: number
    question_type?: string
    difficulty?: string
  }): Promise<any> {
    return request.get('/exams/question-bank/', { params })
  },

  createExam(data: Partial<Exam>): Promise<Exam> {
    return request.post('/exams/exams/', data)
  },

  updateExam(id: number, data: Partial<Exam>): Promise<Exam> {
    return request.put(`/exams/exams/${id}/`, data)
  },

  addQuestions(examId: number, questionIds: number[]): Promise<any> {
    return request.post(`/exams/exams/${examId}/add_questions/`, { question_ids: questionIds })
  },

  gradeAttempt(attemptId: number, data: {
    question_scores?: Record<number, number>
    total_score?: number
    feedback?: string
  }): Promise<ExamAttempt> {
    return request.post(`/exams/attempts/${attemptId}/grade/`, data)
  },

  markCheating(attemptId: number, data: {
    cheating_type: string
    description?: string
    severity?: string
    action_taken?: string
  }): Promise<CheatingRecord> {
    return request.post(`/exams/attempts/${attemptId}/mark_cheating/`, data)
  }
}
