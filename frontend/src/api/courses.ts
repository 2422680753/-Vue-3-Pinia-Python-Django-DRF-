import { request } from './request'

export interface Course {
  id: number
  title: string
  code: string
  description: string
  cover_image: string | null
  category: string
  instructor: any
  price: string
  is_free: boolean
  status: string
  total_enrollments: number
  average_rating: number | null
  rating_count: number
  is_featured: boolean
  is_published: boolean
  difficulty_level: string
  language: string
  created_at: string
  updated_at: string
}

export interface Chapter {
  id: number
  course: number
  title: string
  order: number
  description: string
  is_published: boolean
  lessons_count: number
}

export interface Lesson {
  id: number
  chapter: number
  title: string
  description: string
  order: number
  lesson_type: string
  duration: number
  is_published: boolean
  is_free: boolean
  video_count: number
}

export interface CourseEnrollment {
  id: number
  course: number
  student: number
  role: string
  is_active: boolean
  enrolled_at: string
  progress: number
}

export const courseApi = {
  getCourses(params?: {
    page?: number
    page_size?: number
    category?: string
    difficulty_level?: string
    status?: string
    search?: string
    ordering?: string
  }): Promise<any> {
    return request.get('/courses/courses/', { params })
  },

  getCourseDetail(id: number): Promise<Course> {
    return request.get(`/courses/courses/${id}/`)
  },

  getCourseChapters(courseId: number): Promise<Chapter[]> {
    return request.get(`/courses/chapters/`, { params: { course: courseId } })
  },

  getChapterLessons(chapterId: number): Promise<Lesson[]> {
    return request.get(`/courses/lessons/`, { params: { chapter: chapterId } })
  },

  getMyEnrollments(): Promise<CourseEnrollment[]> {
    return request.get('/courses/enrollments/my-enrollments/')
  },

  enrollCourse(courseId: number): Promise<any> {
    return request.post(`/courses/courses/${courseId}/enroll/`)
  },

  getCourseProgress(courseId: number): Promise<any> {
    return request.get(`/analytics/course-progress/`, { params: { course: courseId } })
  },

  getFeaturedCourses(): Promise<any> {
    return request.get('/courses/courses/featured/')
  }
}
