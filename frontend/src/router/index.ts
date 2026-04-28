import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { title: '注册', requiresAuth: false }
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/views/layout/Layout.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/Dashboard.vue'),
        meta: { title: '学习中心' }
      },
      {
        path: 'courses',
        name: 'Courses',
        component: () => import('@/views/courses/CourseList.vue'),
        meta: { title: '课程列表' }
      },
      {
        path: 'courses/:id',
        name: 'CourseDetail',
        component: () => import('@/views/courses/CourseDetail.vue'),
        meta: { title: '课程详情' }
      },
      {
        path: 'learn/:courseId/lesson/:lessonId',
        name: 'VideoPlayer',
        component: () => import('@/views/player/VideoPlayer.vue'),
        meta: { title: '视频学习' }
      },
      {
        path: 'assignments',
        name: 'Assignments',
        component: () => import('@/views/assignments/AssignmentList.vue'),
        meta: { title: '作业列表' }
      },
      {
        path: 'assignments/:id',
        name: 'AssignmentDetail',
        component: () => import('@/views/assignments/AssignmentDetail.vue'),
        meta: { title: '作业详情' }
      },
      {
        path: 'assignments/submit/:id',
        name: 'AssignmentSubmit',
        component: () => import('@/views/assignments/AssignmentSubmit.vue'),
        meta: { title: '提交作业' }
      },
      {
        path: 'exams',
        name: 'Exams',
        component: () => import('@/views/exams/ExamList.vue'),
        meta: { title: '考试列表' }
      },
      {
        path: 'exams/:id',
        name: 'ExamDetail',
        component: () => import('@/views/exams/ExamDetail.vue'),
        meta: { title: '考试详情' }
      },
      {
        path: 'exam-taking/:attemptId',
        name: 'ExamTaking',
        component: () => import('@/views/exams/ExamTaking.vue'),
        meta: { title: '在线考试' }
      },
      {
        path: 'classes',
        name: 'Classes',
        component: () => import('@/views/classes/ClassList.vue'),
        meta: { title: '我的班级' }
      },
      {
        path: 'classes/:id',
        name: 'ClassDetail',
        component: () => import('@/views/classes/ClassDetail.vue'),
        meta: { title: '班级详情' }
      },
      {
        path: 'analytics',
        name: 'Analytics',
        component: () => import('@/views/analytics/Analytics.vue'),
        meta: { title: '学情分析' }
      },
      {
        path: 'analytics/course/:courseId',
        name: 'CourseAnalytics',
        component: () => import('@/views/analytics/CourseAnalytics.vue'),
        meta: { title: '课程分析' }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/user/Profile.vue'),
        meta: { title: '个人中心' }
      },
      {
        path: 'teacher/courses',
        name: 'TeacherCourses',
        component: () => import('@/views/teacher/CourseManage.vue'),
        meta: { title: '课程管理', roles: ['teacher', 'admin'] }
      },
      {
        path: 'teacher/classes',
        name: 'TeacherClasses',
        component: () => import('@/views/teacher/ClassManage.vue'),
        meta: { title: '班级管理', roles: ['teacher', 'admin'] }
      },
      {
        path: 'teacher/assignments',
        name: 'TeacherAssignments',
        component: () => import('@/views/teacher/AssignmentManage.vue'),
        meta: { title: '作业管理', roles: ['teacher', 'admin'] }
      },
      {
        path: 'teacher/exams',
        name: 'TeacherExams',
        component: () => import('@/views/teacher/ExamManage.vue'),
        meta: { title: '考试管理', roles: ['teacher', 'admin'] }
      },
      {
        path: 'teacher/analytics',
        name: 'TeacherAnalytics',
        component: () => import('@/views/teacher/Analytics.vue'),
        meta: { title: '教学分析', roles: ['teacher', 'admin'] }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/NotFound.vue'),
    meta: { title: '页面不存在' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, _from, next) => {
  document.title = to.meta.title ? `${to.meta.title} - 在线教育平台` : '在线教育平台'
  
  const userStore = useUserStore()
  const token = localStorage.getItem('access_token')
  
  if (to.meta.requiresAuth && !token) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }
  
  if (token && !userStore.userInfo) {
    try {
      await userStore.getUserInfo()
    } catch {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      next({ name: 'Login' })
      return
    }
  }
  
  const roles = to.meta.roles as string[] | undefined
  if (roles && userStore.userInfo) {
    const userRole = userStore.userInfo.role
    if (!roles.includes(userRole)) {
      next({ name: 'Dashboard' })
      return
    }
  }
  
  next()
})

export default router
