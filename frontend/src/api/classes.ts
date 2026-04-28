import { request } from './request'

export interface Class {
  id: number
  name: string
  code: string
  description: string
  course: any
  teacher: any
  assistant_teachers: any[]
  max_students: number
  current_students: number
  start_date: string
  end_date: string
  status: string
  is_private: boolean
  join_code: string | null
  student_count: number
  schedule_count: number
  announcement_count: number
  created_at: string
}

export interface ClassStudent {
  id: number
  class_obj: number
  class_obj_name: string
  student: any
  join_type: string
  is_active: boolean
  dropped_at: string | null
  drop_reason: string | null
  final_grade: string | null
  attendance_rate: number
  is_graduated: boolean
  graduated_at: string | null
  notes: string | null
  enrolled_at: string
}

export interface ClassSchedule {
  id: number
  class_obj: number
  class_obj_name: string
  title: string
  description: string | null
  day_of_week: number
  start_time: string
  end_time: string
  start_date: string
  end_date: string
  is_recurring: boolean
  repeat_weeks: number
  location: string | null
  meeting_url: string | null
  teacher: any | null
  lesson: number | null
  is_active: boolean
  created_at: string
}

export interface ClassAttendance {
  id: number
  schedule: number
  schedule_title: string
  student: any
  attendance_date: string
  status: string
  check_in_time: string | null
  check_out_time: string | null
  notes: string | null
  marked_by: any | null
  created_at: string
}

export interface ClassAnnouncement {
  id: number
  class_obj: number
  class_obj_name: string
  teacher: any
  title: string
  content: string
  priority: string
  is_pinned: boolean
  attachments: string | null
  publish_at: string | null
  expire_at: string | null
  read_count: number
  is_draft: boolean
  created_at: string
}

export interface ClassMaterial {
  id: number
  class_obj: number
  class_obj_name: string
  teacher: any
  title: string
  description: string | null
  file: string
  file_type: string
  file_size: number
  download_count: number
  view_count: number
  is_free: boolean
  is_locked: boolean
  category: string
  created_at: string
}

export const classApi = {
  getMyClasses(): Promise<{
    upcoming: Class[]
    active: Class[]
    completed: Class[]
  }> {
    return request.get('/classes/classes/my_classes/')
  },

  getClassDetail(id: number): Promise<Class> {
    return request.get(`/classes/classes/${id}/`)
  },

  getClassStudents(classId: number): Promise<ClassStudent[]> {
    return request.get('/classes/class-students/', { params: { class_obj: classId } })
  },

  getClassSchedules(classId: number): Promise<ClassSchedule[]> {
    return request.get('/classes/class-schedules/', { params: { class_obj: classId } })
  },

  getClassAnnouncements(classId: number, params?: { is_draft?: boolean }): Promise<ClassAnnouncement[]> {
    return request.get('/classes/class-announcements/', { params: { class_obj: classId, ...params } })
  },

  getClassMaterials(classId: number, params?: { category?: string }): Promise<ClassMaterial[]> {
    return request.get('/classes/class-materials/', { params: { class_obj: classId, ...params } })
  },

  joinClass(joinCode: string): Promise<any> {
    return request.post('/classes/classes/join/', { join_code: joinCode })
  },

  regenerateJoinCode(classId: number): Promise<{ join_code: string }> {
    return request.post(`/classes/classes/${classId}/regenerate_join_code/`)
  },

  addStudent(classId: number, studentId: number): Promise<any> {
    return request.post(`/classes/classes/${classId}/add_student/`, { student_id: studentId })
  },

  removeStudent(classId: number, studentId: number, reason?: string): Promise<any> {
    return request.post(`/classes/classes/${classId}/remove_student/`, { 
      student_id: studentId, 
      reason 
    })
  },

  setGrade(classId: number, data: {
    student_id: number
    final_grade: number
    notes?: string
  }): Promise<ClassStudent> {
    return request.post(`/classes/classes/${classId}/set_grade/`, data)
  },

  graduateStudents(classId: number, data: {
    student_ids: number[]
    final_grade?: number
    notes?: string
  }): Promise<any> {
    return request.post(`/classes/classes/${classId}/graduate/`, data)
  },

  getClassStats(classId: number): Promise<any> {
    return request.get(`/classes/classes/${classId}/stats/`)
  },

  markAttendance(scheduleId: number, data: {
    attendance_date: string
    records: Array<{
      student_id: number
      status: string
      notes?: string
    }>
  }): Promise<any> {
    return request.post(`/classes/class-schedules/${scheduleId}/mark_attendance/`, {
      schedule_id: scheduleId,
      ...data
    })
  },

  getMyAttendance(classId?: number): Promise<ClassAttendance[]> {
    const params = classId ? { class_id: classId } : {}
    return request.get('/classes/class-attendances/my_attendance/', { params })
  },

  createAnnouncement(classId: number, data: Partial<ClassAnnouncement>): Promise<ClassAnnouncement> {
    return request.post('/classes/class-announcements/', { class_obj: classId, ...data })
  },

  updateAnnouncement(id: number, data: Partial<ClassAnnouncement>): Promise<ClassAnnouncement> {
    return request.put(`/classes/class-announcements/${id}/`, data)
  },

  deleteAnnouncement(id: number): Promise<void> {
    return request.delete(`/classes/class-announcements/${id}/`)
  },

  uploadMaterial(classId: number, data: {
    title: string
    description?: string
    file: File
    category?: string
    is_free?: boolean
  }): Promise<ClassMaterial> {
    const formData = new FormData()
    formData.append('class_obj', String(classId))
    formData.append('title', data.title)
    if (data.description) formData.append('description', data.description)
    formData.append('file', data.file)
    if (data.category) formData.append('category', data.category)
    if (data.is_free !== undefined) formData.append('is_free', String(data.is_free))
    
    return request.post('/classes/class-materials/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  downloadMaterial(materialId: number): Promise<any> {
    return request.get(`/classes/class-materials/${materialId}/download/`)
  },

  viewMaterial(materialId: number): Promise<ClassMaterial> {
    return request.get(`/classes/class-materials/${materialId}/view/`)
  },

  createClass(data: Partial<Class>): Promise<Class> {
    return request.post('/classes/classes/', data)
  },

  updateClass(id: number, data: Partial<Class>): Promise<Class> {
    return request.put(`/classes/classes/${id}/`, data)
  },

  createSchedule(classId: number, data: Partial<ClassSchedule>): Promise<ClassSchedule> {
    return request.post('/classes/class-schedules/', { class_obj: classId, ...data })
  },

  updateSchedule(id: number, data: Partial<ClassSchedule>): Promise<ClassSchedule> {
    return request.put(`/classes/class-schedules/${id}/`, data)
  },

  deleteSchedule(id: number): Promise<void> {
    return request.delete(`/classes/class-schedules/${id}/`)
  }
}
