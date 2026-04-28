<template>
  <div class="video-player-container">
    <el-row :gutter="20">
      <el-col :span="18">
        <div class="player-wrapper">
          <div class="video-player" ref="videoContainer">
            <video
              ref="videoRef"
              :poster="lessonInfo?.cover_image"
              class="video-js vjs-big-play-centered"
              playsinline
            />
          </div>
          
          <div class="video-info">
            <h2>{{ lessonInfo?.title }}</h2>
            <div class="video-meta">
              <span>课程：{{ courseInfo?.title }}</span>
              <span>时长：{{ formatDuration(lessonInfo?.duration || 0) }}</span>
              <span>观看次数：{{ videoInfo?.view_count || 0 }}</span>
            </div>
          </div>
          
          <div class="learning-progress">
            <el-progress 
              :percentage="Math.round(progress * 100)" 
              :format="formatProgress"
              :color="progress >= 1 ? '#67C23A' : '#409EFF'"
            />
          </div>
        </div>
        
        <el-card class="chapter-nav">
          <template #header>
            <div class="card-header">
              <span>课程目录</span>
              <el-tag v-if="isComplete" type="success" size="small">已完成</el-tag>
            </div>
          </template>
          
          <div class="chapter-list">
            <div 
              v-for="chapter in chapters" 
              :key="chapter.id"
              class="chapter-item"
            >
              <div class="chapter-header" @click="toggleChapter(chapter.id)">
                <el-icon><component :is="expandedChapters.includes(chapter.id) ? 'ArrowDown' : 'ArrowRight'" /></el-icon>
                <span>{{ chapter.order }}. {{ chapter.title }}</span>
                <el-tag type="info" size="small">
                  {{ chapter.completed_lessons }}/{{ chapter.lessons_count }}
                </el-tag>
              </div>
              
              <div 
                v-show="expandedChapters.includes(chapter.id)"
                class="lesson-list"
              >
                <div 
                  v-for="lesson in getChapterLessons(chapter.id)"
                  :key="lesson.id"
                  class="lesson-item"
                  :class="{ 
                    active: lesson.id === lessonId,
                    completed: isLessonCompleted(lesson.id)
                  }"
                  @click="goToLesson(lesson.id)"
                >
                  <div class="lesson-icon">
                    <el-icon v-if="lesson.id === lessonId"><VideoCamera /></el-icon>
                    <el-icon v-else-if="isLessonCompleted(lesson.id)"><CircleCheck /></el-icon>
                    <el-icon v-else><VideoCamera /></el-icon>
                  </div>
                  <div class="lesson-title">
                    <span>{{ lesson.order }}. {{ lesson.title }}</span>
                    <span class="lesson-duration">{{ formatDuration(lesson.duration) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="notes-card">
          <template #header>
            <div class="card-header">
              <span>学习笔记</span>
              <el-button type="primary" link @click="showNoteDialog = true">
                <el-icon><Edit /></el-icon> 添加笔记
              </el-button>
            </div>
          </template>
          
          <div class="notes-list">
            <div 
              v-for="note in notes" 
              :key="note.id"
              class="note-item"
            >
              <div class="note-time">
                {{ formatTime(note.timestamp) }}
              </div>
              <div class="note-content">{{ note.content }}</div>
              <div class="note-actions">
                <el-button type="primary" link size="small" @click="editNote(note)">编辑</el-button>
                <el-button type="danger" link size="small" @click="deleteNote(note.id)">删除</el-button>
              </div>
            </div>
            
            <el-empty v-if="notes.length === 0" description="暂无笔记" />
          </div>
        </el-card>
        
        <el-card class="material-card" style="margin-top: 20px;">
          <template #header>
            <span>配套资料</span>
          </template>
          
          <div class="material-list">
            <div 
              v-for="material in materials" 
              :key="material.id"
              class="material-item"
            >
              <el-icon class="material-icon"><Document /></el-icon>
              <div class="material-info">
                <div class="material-title">{{ material.title }}</div>
                <div class="material-size">{{ formatFileSize(material.file_size) }}</div>
              </div>
              <el-button type="primary" link @click="downloadMaterial(material)">
                <el-icon><Download /></el-icon>
              </el-button>
            </div>
            
            <el-empty v-if="materials.length === 0" description="暂无资料" />
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-dialog 
      v-model="showNoteDialog" 
      title="添加笔记" 
      width="500px"
    >
      <el-form>
        <el-form-item label="笔记时间">
          <el-input 
            v-model="noteForm.timestamp" 
            :placeholder="currentTimeStr"
            disabled
          />
        </el-form-item>
        <el-form-item label="笔记内容">
          <el-input 
            v-model="noteForm.content" 
            type="textarea"
            :rows="6"
            placeholder="请输入笔记内容..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNoteDialog = false">取消</el-button>
        <el-button type="primary" @click="saveNote">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import videojs from 'video.js'
import 'video.js/dist/video-js.css'
import { videoProgressSocket } from '@/utils/websocket'
import { videoApi, Video, VideoProgress } from '@/api/videos'
import { courseApi, Chapter, Lesson } from '@/api/courses'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()

const courseId = computed(() => parseInt(route.params.courseId as string))
const lessonId = computed(() => parseInt(route.params.lessonId as string))

const videoRef = ref<HTMLVideoElement>()
const videoContainer = ref<HTMLDivElement>()
let player: any = null

const courseInfo = ref<any>()
const lessonInfo = ref<Lesson>()
const videoInfo = ref<Video>()
const progress = ref(0)
const currentTime = ref(0)
const duration = ref(0)
const isComplete = ref(false)

const chapters = ref<Chapter[]>([])
const lessons = ref<Lesson[]>([])
const expandedChapters = ref<number[]>([])

const notes = ref<any[]>([])
const materials = ref<any[]>([])

const showNoteDialog = ref(false)
const noteForm = reactive({
  id: null as number | null,
  timestamp: '00:00:00',
  content: ''
})

const currentTimeStr = computed(() => {
  const seconds = Math.floor(currentTime.value)
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

const formatDuration = (seconds: number) => {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}

const formatProgress = (percentage: number) => {
  return percentage >= 100 ? '已完成' : `${percentage}%`
}

const formatTime = (seconds: number) => {
  return formatDuration(seconds)
}

const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

const getChapterLessons = (chapterId: number) => {
  return lessons.value.filter(l => l.chapter === chapterId)
}

const isLessonCompleted = (lessonId: number) => {
  return false
}

const toggleChapter = (chapterId: number) => {
  const index = expandedChapters.value.indexOf(chapterId)
  if (index > -1) {
    expandedChapters.value.splice(index, 1)
  } else {
    expandedChapters.value.push(chapterId)
  }
}

const goToLesson = (id: number) => {
  router.push(`/learn/${courseId.value}/lesson/${id}`)
}

const initPlayer = async () => {
  if (!videoRef.value) return
  
  player = videojs(videoRef.value, {
    controls: true,
    autoplay: false,
    preload: 'auto',
    language: 'zh-CN',
    controlBar: {
      volumePanel: {
        inline: false
      }
    }
  })
  
  player.src({
    src: videoInfo.value?.video_file || 'https://vjs.zencdn.net/v/oceans.mp4',
    type: 'video/mp4'
  })
  
  player.on('play', handlePlay)
  player.on('pause', handlePause)
  player.on('timeupdate', handleTimeUpdate)
  player.on('ended', handleEnded)
  player.on('loadedmetadata', handleLoadedMetadata)
  
  if (progress.value > 0 && progress.value < 1) {
    player.currentTime(progress.value * duration.value)
  }
}

const handlePlay = () => {
  sendProgressUpdate(true)
  
  videoProgressSocket.send({
    type: 'activity',
    data: {
      event_type: 'play',
      video_id: videoInfo.value?.id
    }
  })
}

const handlePause = () => {
  sendProgressUpdate(false)
  
  videoProgressSocket.send({
    type: 'activity',
    data: {
      event_type: 'pause',
      video_id: videoInfo.value?.id
    }
  })
}

const handleTimeUpdate = () => {
  if (!player) return
  currentTime.value = player.currentTime()
  duration.value = player.duration()
  
  if (duration.value > 0) {
    progress.value = currentTime.value / duration.value
  }
}

const handleEnded = async () => {
  isComplete.value = true
  progress.value = 1
  
  if (videoInfo.value) {
    await videoApi.completeVideo(videoInfo.value.id)
  }
  
  videoProgressSocket.send({
    type: 'progress',
    data: {
      video_id: videoInfo.value?.id,
      progress: 1,
      current_time: duration.value,
      duration: duration.value,
      is_playing: false,
      is_complete: true
    }
  })
}

const handleLoadedMetadata = () => {
  if (!player) return
  duration.value = player.duration()
  
  if (progress.value > 0 && progress.value < 1) {
    player.currentTime(progress.value * duration.value)
  }
}

let progressTimer: number | null = null

const sendProgressUpdate = (isPlaying: boolean) => {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
  
  const sendUpdate = async () => {
    if (!videoInfo.value || !player) return
    
    try {
      await videoApi.updateProgress({
        video_id: videoInfo.value.id,
        current_time: player.currentTime(),
        duration: player.duration(),
        is_playing: isPlaying
      })
      
      videoProgressSocket.send({
        type: 'progress',
        data: {
          video_id: videoInfo.value.id,
          progress: progress.value,
          current_time: player.currentTime(),
          duration: player.duration(),
          is_playing: isPlaying
        }
      })
    } catch (error) {
      console.error('Progress update failed:', error)
    }
  }
  
  sendUpdate()
  
  if (isPlaying) {
    progressTimer = window.setInterval(sendUpdate, 5000)
  }
}

const connectWebSocket = () => {
  if (!videoInfo.value) return
  
  videoProgressSocket.connect(`/ws/video/progress/${videoInfo.value.id}/`, {
    onMessage: (data: any) => {
      console.log('WebSocket message:', data)
    }
  })
}

const loadData = async () => {
  try {
    const courseData = await courseApi.getCourseDetail(courseId.value)
    courseInfo.value = courseData
    
    const chaptersData = await courseApi.getCourseChapters(courseId.value)
    chapters.value = chaptersData
    expandedChapters.value = chaptersData.map((c: Chapter) => c.id)
    
    if (lessonId.value) {
      const videos = await videoApi.getVideoByLesson(lessonId.value)
      if (videos.length > 0) {
        videoInfo.value = videos[0]
        
        try {
          const progressData = await videoApi.getVideoProgress(videoInfo.value.id)
          progress.value = progressData.progress || 0
          isComplete.value = progressData.is_completed
        } catch {
          progress.value = 0
        }
      }
    }
  } catch (error) {
    console.error('Failed to load data:', error)
  }
}

const saveNote = async () => {
  if (noteForm.id) {
    const index = notes.value.findIndex(n => n.id === noteForm.id)
    if (index > -1) {
      notes.value[index] = { ...notes.value[index], ...noteForm }
    }
  } else {
    notes.value.push({
      id: Date.now(),
      timestamp: currentTime.value,
      content: noteForm.content
    })
  }
  
  showNoteDialog.value = false
  noteForm.id = null
  noteForm.content = ''
}

const editNote = (note: any) => {
  noteForm.id = note.id
  noteForm.timestamp = formatTime(note.timestamp)
  noteForm.content = note.content
  showNoteDialog.value = true
}

const deleteNote = (id: number) => {
  const index = notes.value.findIndex(n => n.id === id)
  if (index > -1) {
    notes.value.splice(index, 1)
  }
}

const downloadMaterial = (material: any) => {
  console.log('Download material:', material)
}

watch(showNoteDialog, (val) => {
  if (val && !noteForm.id) {
    noteForm.timestamp = currentTimeStr.value
  }
})

onMounted(async () => {
  await loadData()
  
  await nextTick()
  if (videoInfo.value) {
    await initPlayer()
    connectWebSocket()
  }
})

onUnmounted(() => {
  if (player) {
    player.dispose()
  }
  if (progressTimer) {
    clearInterval(progressTimer)
  }
  videoProgressSocket.disconnect()
})
</script>

<style scoped lang="scss">
.video-player-container {
  .player-wrapper {
    background: #fff;
    border-radius: 4px;
    padding: 20px;
    margin-bottom: 20px;
    
    .video-player {
      background: #000;
      border-radius: 8px;
      overflow: hidden;
      
      :deep(.video-js) {
        width: 100%;
        height: 450px;
      }
    }
    
    .video-info {
      margin-top: 16px;
      
      h2 {
        font-size: 18px;
        font-weight: 600;
        margin: 0 0 12px;
      }
      
      .video-meta {
        font-size: 14px;
        color: #909399;
        
        span {
          margin-right: 24px;
        }
      }
    }
    
    .learning-progress {
      margin-top: 16px;
      padding: 16px;
      background: #f5f7fa;
      border-radius: 8px;
    }
  }
  
  .chapter-nav {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    
    .chapter-list {
      .chapter-item {
        border-bottom: 1px solid #ebeef5;
        
        &:last-child {
          border-bottom: none;
        }
        
        .chapter-header {
          display: flex;
          align-items: center;
          padding: 12px 8px;
          cursor: pointer;
          font-weight: 500;
          
          &:hover {
            background: #f5f7fa;
          }
          
          span {
            margin-left: 8px;
            flex: 1;
          }
        }
        
        .lesson-list {
          padding: 0 0 8px;
          
          .lesson-item {
            display: flex;
            align-items: center;
            padding: 8px 8px 8px 32px;
            cursor: pointer;
            
            &:hover {
              background: #f5f7fa;
            }
            
            &.active {
              background: #ecf5ff;
              
              .lesson-icon {
                color: #409EFF;
              }
            }
            
            &.completed {
              .lesson-icon {
                color: #67C23A;
              }
            }
            
            .lesson-icon {
              margin-right: 8px;
              color: #909399;
            }
            
            .lesson-title {
              flex: 1;
              display: flex;
              justify-content: space-between;
              align-items: center;
              font-size: 14px;
              
              .lesson-duration {
                color: #909399;
                font-size: 12px;
              }
            }
          }
        }
      }
    }
  }
  
  .notes-card,
  .material-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    
    .notes-list {
      max-height: 300px;
      overflow-y: auto;
      
      .note-item {
        padding: 12px 0;
        border-bottom: 1px solid #ebeef5;
        
        &:last-child {
          border-bottom: none;
        }
        
        .note-time {
          font-size: 12px;
          color: #409EFF;
          margin-bottom: 4px;
        }
        
        .note-content {
          font-size: 14px;
          color: #606266;
          line-height: 1.6;
          margin-bottom: 8px;
        }
        
        .note-actions {
          display: flex;
          gap: 8px;
        }
      }
    }
    
    .material-list {
      .material-item {
        display: flex;
        align-items: center;
        padding: 12px 0;
        border-bottom: 1px solid #ebeef5;
        
        &:last-child {
          border-bottom: none;
        }
        
        .material-icon {
          font-size: 24px;
          color: #409EFF;
          margin-right: 12px;
        }
        
        .material-info {
          flex: 1;
          
          .material-title {
            font-size: 14px;
            font-weight: 500;
          }
          
          .material-size {
            font-size: 12px;
            color: #909399;
            margin-top: 4px;
          }
        }
      }
    }
  }
}
</style>
