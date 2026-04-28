import { request } from './request'

export interface Assignment {
  id: number
  course: number
  chapter: number | null
  title: string
  description: string
  assignment_type: string
  max_score: number
  pass_score: number
  due_date: string
  allow_late_submission: boolean
  late_penalty_rate: number
  allow_resubmit: boolean
  max_resubmissions: number
  allow_peer_review: boolean
  status: string
  is_published: boolean
  published_at: string | null
  total_submissions: number
  created_at: string
}

export interface AssignmentQuestion {
  id: number
  assignment: number
  question_text: string
  question_type: string
  order: number
  score: number
  options: any[]
  correct_answer: any
  explanation: string | null
}

export interface AssignmentSubmission {
  id: number
  assignment: number
  student: any
  submission_number: number
  content: string
  submitted_file: string | null
  submitted_at: string | null
  status: string
  total_score: number | null
  score_percentage: number | null
  is_passed: boolean | null
  feedback: string | null
  graded_at: string | null
  graded_by: any | null
  created_at: string
}

export interface SubmissionFeedback {
  id: number
  submission: number
  grader: any
  comment: string
  score: number | null
  created_at: string
}

export const assignmentApi = {
  getMyAssignments(params?: {
    course?: number
    status?: string
    ordering?: string
  }): Promise<any> {
    return request.get('/assignments/assignments/my-assignments/', { params })
  },

  getAssignmentDetail(id: number): Promise<Assignment> {
    return request.get(`/assignments/assignments/${id}/`)
  },

  getAssignmentQuestions(assignmentId: number): Promise<AssignmentQuestion[]> {
    return request.get(`/assignments/questions/`, { params: { assignment: assignmentId } })
  },

  getMySubmission(assignmentId: number): Promise<AssignmentSubmission> {
    return request.get(`/assignments/submissions/my-submissions/?assignment=${assignmentId}`)
  },

  submitAssignment(assignmentId: number, data: {
    content?: string
    submitted_file?: File
    answers?: any[]
  }): Promise<AssignmentSubmission> {
    const formData = new FormData()
    if (data.content) formData.append('content', data.content)
    if (data.submitted_file) formData.append('submitted_file', data.submitted_file)
    if (data.answers) formData.append('answers', JSON.stringify(data.answers))
    
    return request.post(`/assignments/assignments/${assignmentId}/submit/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  resubmitAssignment(submissionId: number, data: {
    content?: string
    submitted_file?: File
  }): Promise<AssignmentSubmission> {
    const formData = new FormData()
    if (data.content) formData.append('content', data.content)
    if (data.submitted_file) formData.append('submitted_file', data.submitted_file)
    
    return request.post(`/assignments/submissions/${submissionId}/resubmit/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  getSubmissionDetail(id: number): Promise<AssignmentSubmission> {
    return request.get(`/assignments/submissions/${id}/`)
  },

  getSubmissionFeedback(submissionId: number): Promise<SubmissionFeedback[]> {
    return request.get(`/assignments/feedbacks/?submission=${submissionId}`)
  },

  getTeacherAssignments(params?: {
    course?: number
    status?: string
  }): Promise<any> {
    return request.get('/assignments/assignments/', { params })
  },

  getSubmissionsByAssignment(assignmentId: number, params?: {
    status?: string
  }): Promise<any> {
    return request.get(`/assignments/assignments/${assignmentId}/submissions/`, { params })
  },

  gradeSubmission(submissionId: number, data: {
    total_score: number
    feedback?: string
    question_scores?: Record<number, number>
  }): Promise<any> {
    return request.post(`/assignments/submissions/${submissionId}/grade/`, data)
  },

  batchGrade(assignmentId: number, data: {
    grades: Array<{
      submission_id: number
      total_score: number
      feedback?: string
    }>
  }): Promise<any> {
    return request.post(`/assignments/assignments/${assignmentId}/batch-grade/`, data)
  }
}
