<template>
  <div class="course-list-container">
    <div class="search-bar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索课程..."
        prefix-icon="Search"
        clearable
        style="width: 300px;"
        @change="loadCourses"
      />
      
      <el-select v-model="selectedCategory" placeholder="选择分类" style="width: 200px;" @change="loadCourses">
        <el-option label="全部分类" value="" />
        <el-option label="编程语言" value="programming" />
        <el-option label="前端开发" value="frontend" />
        <el-option label="后端开发" value="backend" />
        <el-option label="数据库" value="database" />
      </el-select>
      
      <el-select v-model="selectedLevel" placeholder="难度级别" style="width: 150px;" @change="loadCourses">
        <el-option label="全部级别" value="" />
        <el-option label="入门" value="beginner" />
        <el-option label="中级" value="intermediate" />
        <el-option label="高级" value="advanced" />
      </el-select>
      
      <el-button type="primary" @click="loadCourses">
        <el-icon><Search /></el-icon>
        搜索
      </el-button>
    </div>
    
    <el-tabs v-model="activeTab" class="course-tabs">
      <el-tab-pane label="全部课程" name="all">
        <el-row :gutter="20">
          <el-col :span="6" v-for="course in courses" :key="course.id">
            <el-card shadow="hover" class="course-card" @click="goToCourse(course.id)">
              <div class="course-cover">
                <img :src="course.cover_image || defaultCover" :alt="course.title" />
                <div class="course-status">
                  <el-tag v-if="course.status === 'published'" type="success" size="small">已发布</el-tag>
                  <el-tag v-else type="info" size="small">{{ course.status }}</el-tag>
                </div>
              </div>
              
              <div class="course-info">
                <h3 class="course-title">{{ course.title }}</h3>
                <p class="course-desc">{{ course.description || '暂无描述' }}</p>
                
                <div class="course-meta">
                  <span class="teacher">
                    <el-icon><User /></el-icon>
                    {{ course.teacher_name || '未知教师' }}
                  </span>
                  <span class="students">
                    <el-icon><UserFilled /></el-icon>
                    {{ course.enrollment_count || 0 }} 人学习
                  </span>
                </div>
                
                <div class="course-footer">
                  <el-rate v-model="course.rating" disabled :max="5" :show-text="false" />
                  <span class="price" v-if="course.price > 0">¥{{ course.price }}</span>
                  <span class="price" v-else>免费</span>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
        
        <el-empty v-if="courses.length === 0" description="暂无课程" />
        
        <div class="pagination" v-if="total > 0">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[12, 24, 48]"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="loadCourses"
            @current-change="loadCourses"
          />
        </div>
      </el-tab-pane>
      
      <el-tab-pane label="我的课程" name="my">
        <el-row :gutter="20">
          <el-col :span="6" v-for="enrollment in myCourses" :key="enrollment.id">
            <el-card shadow="hover" class="course-card" @click="goToCourse(enrollment.course.id)">
              <div class="course-cover">
                <img :src="enrollment.course.cover_image || defaultCover" :alt="enrollment.course.title" />
                <div class="progress-overlay">
                  <el-progress 
                    type="circle" 
                    :percentage="Math.round((enrollment.progress || 0) * 100)" 
                    :width="60"
                  />
                </div>
              </div>
              
              <div class="course-info">
                <h3 class="course-title">{{ enrollment.course.title }}</h3>
                
                <div class="course-meta">
                  <span>进度: {{ Math.round((enrollment.progress || 0) * 100) }}%</span>
                </div>
                
                <div class="last-learn">
                  <span>最近学习: {{ enrollment.last_access_at ? formatDate(enrollment.last_access_at) : '未开始' }}</span>
                </div>
                
                <div class="course-footer">
                  <el-button type="primary" link @click.stop="continueLearn(enrollment.course.id)">
                    继续学习
                  </el-button>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
        
        <el-empty v-if="myCourses.length === 0" description="暂无已报名课程">
          <el-button type="primary" @click="activeTab = 'all'">去选课</el-button>
        </el-empty>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { courseApi, Course, Enrollment } from '@/api/courses'
import dayjs from 'dayjs'

const router = useRouter()

const defaultCover = 'https://cube.elemecdn.com/6/94/4d3ea53c084bad6931a56d5158a48jpeg.jpeg'

const activeTab = ref('all')
const searchKeyword = ref('')
const selectedCategory = ref('')
const selectedLevel = ref('')

const courses = ref<Course[]>([])
const myCourses = ref<any[]>([])

const currentPage = ref(1)
const pageSize = ref(12)
const total = ref(0)

const formatDate = (date: string) => {
  return dayjs(date).format('MM-DD HH:mm')
}

const goToCourse = (courseId: number) => {
  router.push(`/courses/${courseId}`)
}

const continueLearn = (courseId: number) => {
  router.push(`/learn/${courseId}`)
}

const loadCourses = async () => {
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    
    if (searchKeyword.value) {
      params.search = searchKeyword.value
    }
    if (selectedCategory.value) {
      params.category = selectedCategory.value
    }
    if (selectedLevel.value) {
      params.level = selectedLevel.value
    }
    params.status = 'published'
    
    const response = await courseApi.getCourses(params)
    courses.value = response.results
    total.value = response.count
  } catch (error) {
    console.error('Failed to load courses:', error)
  }
}

const loadMyCourses = async () => {
  try {
    const response = await courseApi.getMyCourses()
    myCourses.value = response.results || []
  } catch (error) {
    console.error('Failed to load my courses:', error)
  }
}

watch(activeTab, (val) => {
  if (val === 'my') {
    loadMyCourses()
  } else {
    loadCourses()
  }
})

onMounted(() => {
  loadCourses()
})
</script>

<style scoped lang="scss">
.course-list-container {
  .search-bar {
    display: flex;
    gap: 16px;
    margin-bottom: 20px;
  }
  
  .course-tabs {
    :deep(.el-tabs__header) {
      margin-bottom: 20px;
    }
  }
  
  .course-card {
    margin-bottom: 20px;
    cursor: pointer;
    transition: transform 0.3s, box-shadow 0.3s;
    
    &:hover {
      transform: translateY(-4px);
    }
    
    .course-cover {
      position: relative;
      height: 150px;
      margin: -20px -20px 16px;
      border-radius: 4px 4px 0 0;
      overflow: hidden;
      
      img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
      
      .course-status {
        position: absolute;
        top: 12px;
        right: 12px;
      }
      
      .progress-overlay {
        position: absolute;
        bottom: 12px;
        right: 12px;
        background: rgba(255, 255, 255, 0.9);
        border-radius: 50%;
        padding: 4px;
      }
    }
    
    .course-info {
      .course-title {
        font-size: 16px;
        font-weight: 600;
        margin: 0 0 8px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      
      .course-desc {
        font-size: 13px;
        color: #909399;
        margin: 0 0 12px;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        height: 36px;
      }
      
      .course-meta {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
        color: #909399;
        margin-bottom: 12px;
        
        .teacher,
        .students {
          display: flex;
          align-items: center;
          
          .el-icon {
            margin-right: 4px;
          }
        }
      }
      
      .last-learn {
        font-size: 12px;
        color: #909399;
        margin-bottom: 8px;
      }
      
      .course-footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-top: 12px;
        border-top: 1px solid #ebeef5;
        
        .price {
          font-size: 16px;
          font-weight: 600;
          color: #f56c6c;
        }
      }
    }
  }
  
  .pagination {
    display: flex;
    justify-content: center;
    margin-top: 20px;
  }
}
</style>
