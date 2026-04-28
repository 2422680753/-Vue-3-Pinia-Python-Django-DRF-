<template>
  <div class="dashboard-container">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
              <el-icon :size="24"><Reading /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.courses }}</div>
              <div class="stat-label">学习课程</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
              <el-icon :size="24"><Timer /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ formatDuration(stats.totalStudyTime) }}</div>
              <div class="stat-label">本周学习时长</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
              <el-icon :size="24"><Trophy /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.learningStreak }}</div>
              <div class="stat-label">连续学习天数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
              <el-icon :size="24"><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.completedLessons }}</div>
              <div class="stat-label">完成课时</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" class="mt-20">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>学习进度</span>
              <el-link type="primary" @click="$router.push('/courses')">查看全部</el-link>
            </div>
          </template>
          
          <el-table :data="courseProgress" style="width: 100%">
            <el-table-column prop="course_title" label="课程" width="200">
              <template #default="scope">
                <div class="course-name">
                  <el-avatar :size="40" :src="scope.row.cover_image">
                    <el-icon><Reading /></el-icon>
                  </el-avatar>
                  <span>{{ scope.row.course_title }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="progress" label="进度" min-width="200">
              <template #default="scope">
                <el-progress 
                  :percentage="Math.round(scope.row.overall_progress * 100)" 
                  :color="getProgressColor(scope.row.overall_progress)"
                />
              </template>
            </el-table-column>
            <el-table-column prop="completed_lessons" label="完成课时">
              <template #default="scope">
                <span>{{ scope.row.completed_lessons }} / {{ scope.row.total_lessons }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="last_access_at" label="最后学习">
              <template #default="scope">
                <span>{{ formatDate(scope.row.last_access_at) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="scope">
                <el-button type="primary" link @click="goToCourse(scope.row.course_id)">
                  继续学习
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          
          <el-empty v-if="courseProgress.length === 0" description="暂无学习进度">
            <el-button type="primary" @click="$router.push('/courses')">去选课</el-button>
          </el-empty>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <span>待办事项</span>
          </template>
          
          <el-timeline>
            <el-timeline-item
              v-for="(item, index) in todoList"
              :key="index"
              :timestamp="item.deadline"
              placement="top"
              :type="item.type"
            >
              <div class="todo-item">
                <div class="todo-title">{{ item.title }}</div>
                <div class="todo-desc">{{ item.description }}</div>
                <el-tag :type="item.tagType" size="small">{{ item.status }}</el-tag>
              </div>
            </el-timeline-item>
            
            <el-timeline-item v-if="todoList.length === 0" placement="top">
              <div class="todo-empty">
                <el-icon :size="32" color="#909399"><CircleCheck /></el-icon>
                <p>所有任务已完成！</p>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" class="mt-20">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>近7天学习时长</span>
          </template>
          <div class="chart-container">
            <Bar :data="chartData" :options="chartOptions" />
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>最近公告</span>
          </template>
          
          <div class="announcement-list">
            <div 
              v-for="(item, index) in announcements" 
              :key="index" 
              class="announcement-item"
            >
              <div class="announcement-header">
                <span class="announcement-title">{{ item.title }}</span>
                <el-tag v-if="item.is_pinned" type="danger" size="small">置顶</el-tag>
              </div>
              <div class="announcement-content">{{ item.content }}</div>
              <div class="announcement-footer">
                <span class="author">{{ item.teacher_name }}</span>
                <span class="date">{{ formatDate(item.created_at) }}</span>
              </div>
            </div>
            
            <el-empty v-if="announcements.length === 0" description="暂无公告" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'
import dayjs from 'dayjs'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
)

const router = useRouter()

const stats = reactive({
  courses: 0,
  totalStudyTime: 0,
  learningStreak: 0,
  completedLessons: 0
})

const courseProgress = ref<any[]>([])
const todoList = ref<any[]>([])
const announcements = ref<any[]>([])

const chartData = reactive({
  labels: [],
  datasets: [
    {
      label: '学习时长(分钟)',
      backgroundColor: '#409EFF',
      data: []
    }
  ]
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false
    }
  },
  scales: {
    y: {
      beginAtZero: true
    }
  }
}

const formatDuration = (seconds: number) => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) {
    return `${hours}小时${minutes}分钟`
  }
  return `${minutes}分钟`
}

const formatDate = (date: string | null) => {
  if (!date) return '暂无'
  return dayjs(date).format('MM-DD HH:mm')
}

const getProgressColor = (progress: number) => {
  if (progress >= 0.8) return '#67C23A'
  if (progress >= 0.5) return '#E6A23C'
  return '#409EFF'
}

const goToCourse = (courseId: number) => {
  router.push(`/courses/${courseId}`)
}

const loadDashboardData = () => {
  const now = dayjs()
  const labels = []
  const data = []
  
  for (let i = 6; i >= 0; i--) {
    const date = now.subtract(i, 'day')
    labels.push(date.format('MM-DD'))
    data.push(Math.floor(Math.random() * 120) + 30)
  }
  
  chartData.labels = labels
  chartData.datasets[0].data = data
  
  stats.courses = 3
  stats.totalStudyTime = 12600
  stats.learningStreak = 7
  stats.completedLessons = 15
  
  courseProgress.value = [
    {
      course_id: 1,
      course_title: 'Python 编程入门',
      cover_image: '',
      overall_progress: 0.75,
      completed_lessons: 12,
      total_lessons: 16,
      last_access_at: now.toISOString()
    },
    {
      course_id: 2,
      course_title: 'Vue 3 实战开发',
      cover_image: '',
      overall_progress: 0.45,
      completed_lessons: 9,
      total_lessons: 20,
      last_access_at: now.subtract(1, 'day').toISOString()
    },
    {
      course_id: 3,
      course_title: '数据库设计与优化',
      cover_image: '',
      overall_progress: 0.2,
      completed_lessons: 3,
      total_lessons: 15,
      last_access_at: now.subtract(3, 'day').toISOString()
    }
  ]
  
  todoList.value = [
    {
      title: '完成 Python 第三章作业',
      description: '截止时间：今天 23:59',
      deadline: '今天 23:59',
      status: '待提交',
      tagType: 'danger',
      type: 'warning'
    },
    {
      title: '查看作业批改结果',
      description: 'Vue 第二章作业已批改',
      deadline: '昨天 18:30',
      status: '已完成',
      tagType: 'success',
      type: 'primary'
    },
    {
      title: '准备明天的考试',
      description: '数据库期中考试',
      deadline: '明天 09:00',
      status: '待考试',
      tagType: 'warning',
      type: 'info'
    }
  ]
  
  announcements.value = [
    {
      title: '关于课程进度的重要通知',
      content: '本周课程内容已更新，请各位同学及时学习...',
      is_pinned: true,
      teacher_name: '张老师',
      created_at: now.toISOString()
    },
    {
      title: '期中考试安排',
      content: '期中考试将于下周六举行，请做好复习准备...',
      is_pinned: false,
      teacher_name: '李老师',
      created_at: now.subtract(1, 'day').toISOString()
    }
  ]
}

onMounted(() => {
  loadDashboardData()
})
</script>

<style scoped lang="scss">
.dashboard-container {
  .stat-card {
    .stat-content {
      display: flex;
      align-items: center;
      
      .stat-icon {
        width: 60px;
        height: 60px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fff;
        margin-right: 16px;
      }
      
      .stat-info {
        .stat-value {
          font-size: 28px;
          font-weight: bold;
          color: #303133;
        }
        
        .stat-label {
          font-size: 14px;
          color: #909399;
          margin-top: 4px;
        }
      }
    }
  }
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .course-name {
    display: flex;
    align-items: center;
    
    span {
      margin-left: 12px;
      font-weight: 500;
    }
  }
  
  .chart-container {
    height: 300px;
  }
  
  .todo-item {
    .todo-title {
      font-weight: 500;
      margin-bottom: 4px;
    }
    
    .todo-desc {
      font-size: 13px;
      color: #909399;
      margin-bottom: 8px;
    }
  }
  
  .todo-empty {
    text-align: center;
    padding: 20px;
    color: #909399;
    
    p {
      margin-top: 12px;
    }
  }
  
  .announcement-list {
    .announcement-item {
      padding: 16px 0;
      border-bottom: 1px solid #ebeef5;
      
      &:last-child {
        border-bottom: none;
      }
      
      .announcement-header {
        display: flex;
        align-items: center;
        margin-bottom: 8px;
        
        .announcement-title {
          font-weight: 500;
          margin-right: 8px;
        }
      }
      
      .announcement-content {
        font-size: 14px;
        color: #606266;
        margin-bottom: 8px;
        line-height: 1.6;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
      }
      
      .announcement-footer {
        font-size: 12px;
        color: #909399;
        
        .author {
          margin-right: 16px;
        }
      }
    }
  }
  
  .mt-20 {
    margin-top: 20px;
  }
}
</style>
