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
          
          <div class="sync-status" v-if="syncStatus !== 'idle'">
            <el-icon v-if="syncStatus === 'syncing'" class="syncing"><Loading /></el-icon>
            <el-icon v-else-if="syncStatus === 'synced'" class="synced"><CircleCheck /></el-icon>
            <el-icon v-else-if="syncStatus === 'error'" class="error"><Warning /></el-icon>
            <span>{{ syncStatusText }}</span>
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
    
    <el-dialog
      v-model="showConflictDialog"
      title="进度冲突"
      width="400px"
    >
      <div class="conflict-info">
        <el-icon :size="48" color="#E6A23C"><Warning /></el-icon>
        <p>检测到其他设备的播放进度较新，是否同步？</p>
        <div class="conflict-details">
          <div class="conflict-item">
            <span>当前设备进度：</span>
            <span class="local">{{ formatDuration(localProgressTime) }}</span>
          </div>
          <div class="conflict-item">
            <span>服务器最新进度：</span>
            <span class="server">{{ formatDuration(serverProgressTime) }}</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="useLocalProgress">使用当前进度</el-button>
        <el-button type="primary" @click="useServerProgress">同步服务器进度</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import videojs from 'video.js'
import 'video.js/dist/video-js.css'
import { createVideoProgressSync, type ProgressState } from '@/utils/videoProgressSync'
import { videoApi, Video } from '@/api/videos'
import { courseApi, Chapter, Lesson } from '@/api/courses'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()

const courseId = computed(() => parseInt(route.params.courseId as string))
const lessonId = computed(() => parseInt(route.params.lessonId as string))

const videoRef = ref<HTMLVideoElement>()
const videoContainer = ref<HTMLDivElement>()
let player: any = null

let syncManager: ReturnType<typeof createVideoProgressSync> | null = null

const courseInfo = ref<any>()
const lessonInfo = ref<Lesson>()
const videoInfo = ref<Video>()
const progress = ref(0)
const currentTime = ref(0)
const duration = ref(0)
const isComplete = ref(false)
const version = ref(1)

const syncStatus = ref<'idle' | 'syncing' | 'synced' | 'error'>('idle')
const syncStatusText = computed(() => {
  switch (syncStatus.value) {
    case 'syncing': return '同步中...'
    case 'synced': return '已同步'
    case 'error': return '同步失败'
    default: return ''
  }
})

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

const showConflictDialog = ref(false)
const localProgressTime = ref(0)
const serverProgressTime = ref(0)

const currentTimeStr = computed(() => {
  const seconds = Math.floor(currentTime.value)
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

const formatDuration = (seconds: number) => {
  if (!seconds || seconds <= 0) return '00:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

const formatProgress = (percentage: number) => {
  return percentage >= 100 ? '已完成' : `${percentage}%`
}

const formatTime = (seconds: number) => {
  return formatDuration(seconds)
}

const formatFileSize = (bytes: number) => {
  if (!bytes) return '0 B'
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

const goToLesson = async (id: number) => {
  if (id === lessonId.value) return
  
  if (syncManager) {
    syncManager.setPlaying(false)
  }
  
  router.push(`/learn/${courseId.value}/lesson/${id}`)
}

const handleProgressUpdate = (state: ProgressState) => {
  progress.value = state.progress
  currentTime.value = state.currentTime
  duration.value = state.totalDuration
  isComplete.value = state.isCompleted
  version.value = state.version
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
  player.on('seeking', handleSeeking)
  player.on('seeked', handleSeeked)
  player.on('waiting', handleWaiting)
  player.on('playing', handlePlaying)
  
  if (progress.value > 0 && progress.value < 1 && duration.value > 0) {
    const targetTime = progress.value * duration.value
    player.currentTime(targetTime)
    currentTime.value = targetTime
  }
}

const handlePlay = () => {
  if (syncManager) {
    syncManager.setPlaying(true)
  }
  
  syncStatus.value = 'syncing'
}

const handlePause = () => {
  if (syncManager) {
    syncManager.setPlaying(false)
  }
  
  syncStatus.value = 'synced'
}

const handleTimeUpdate = () => {
  if (!player) return
  
  const time = player.currentTime()
  const dur = player.duration()
  
  if (!isNaN(dur) && dur > 0) {
    duration.value = dur
  }
  
  currentTime.value = time
  
  if (duration.value > 0) {
    progress.value = Math.min(time / duration.value, 1)
  }
  
  if (syncManager && !isNaN(dur)) {
    syncManager.setProgress(time, dur)
  }
}

const handleSeeking = () => {
  if (syncManager && player) {
    const current = player.currentTime()
    syncManager.startSeek(current)
  }
}

const handleSeeked = () => {
  if (syncManager && player) {
    const toTime = player.currentTime()
    syncManager.endSeek(toTime)
    
    syncStatus.value = 'syncing'
    setTimeout(() => {
      syncStatus.value = 'synced'
    }, 500)
  }
}

const handleWaiting = () => {
  syncStatus.value = 'syncing'
}

const handlePlaying = () => {
  syncStatus.value = 'synced'
}

const handleEnded = async () => {
  isComplete.value = true
  progress.value = 1
  
  if (syncManager) {
    syncManager.setPlaying(false)
    await syncManager.complete()
  }
  
  if (videoInfo.value) {
    try {
      await videoApi.completeVideo(videoInfo.value.id)
    } catch (error) {
      console.error('Failed to mark as complete:', error)
    }
  }
  
  ElMessage({
    message: '恭喜！您已完成本课时学习',
    type: 'success',
    duration: 3000
  })
}

const handleLoadedMetadata = () => {
  if (!player) return
  
  const dur = player.duration()
  if (!isNaN(dur)) {
    duration.value = dur
    
    if (progress.value > 0 && progress.value < 1) {
      const targetTime = progress.value * duration.value
      player.currentTime(targetTime)
      currentTime.value = targetTime
    }
  }
}

const initSyncManager = async () => {
  if (!lessonId.value) return
  
  syncManager = createVideoProgressSync({
    debounceInterval: 3000,
    maxInterval: 15000,
    maxRetries: 3,
    retryDelay: 2000,
    syncOnVisibilityChange: true
  })
  
  await syncManager.init(lessonId.value, handleProgressUpdate)
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
      }
      
      try {
        const progressData = await videoApi.getVideoProgress(lessonId.value)
        progress.value = progressData.progress || 0
        isComplete.value = progressData.is_completed || false
        currentTime.value = progressData.current_time || 0
        duration.value = progressData.total_duration || 0
        version.value = progressData.version || 1
      } catch (error) {
        console.warn('No progress found:', error)
        progress.value = 0
      }
    }
  } catch (error) {
    console.error('Failed to load data:', error)
    ElMessage.error('加载视频数据失败')
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

const useLocalProgress = () => {
  showConflictDialog.value = false
  
  if (syncManager && player) {
    player.currentTime(localProgressTime.value)
    syncManager.setProgress(localProgressTime.value, duration.value)
  }
}

const useServerProgress = () => {
  showConflictDialog.value = false
  
  if (syncManager && player) {
    player.currentTime(serverProgressTime.value)
    syncManager.setProgress(serverProgressTime.value, duration.value)
    
    currentTime.value = serverProgressTime.value
    if (duration.value > 0) {
      progress.value = serverProgressTime.value / duration.value
    }
  }
}

watch(showNoteDialog, (val) => {
  if (val && !noteForm.id) {
    noteForm.timestamp = currentTimeStr.value
  }
})

watch(lessonId, async (newId, oldId) => {
  if (newId && newId !== oldId) {
    if (syncManager) {
      await syncManager.destroy()
    }
    
    await loadData()
    
    if (player) {
      player.dispose()
      player = null
    }
    
    await nextTick()
    await initPlayer()
    await initSyncManager()
  }
})

onMounted(async () => {
  await loadData()
  
  await nextTick()
  if (videoInfo.value || lessonId.value) {
    await initPlayer()
    await initSyncManager()
  }
})

onUnmounted(async () => {
  if (player) {
    player.dispose()
  }
  
  if (syncManager) {
    await syncManager.destroy()
  }
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
    
    .sync-status {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      padding: 8px 0;
      font-size: 12px;
      color: #909399;
      
      .syncing {
        animation: spin 1s linear infinite;
      }
      
      .synced {
        color: #67C23A;
      }
      
      .error {
        color: #F56C6C;
      }
      
      .el-icon {
        margin-right: 4px;
      }
    }
    
    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
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
  
  .conflict-info {
    text-align: center;
    padding: 20px 0;
    
    .el-icon {
      margin-bottom: 16px;
    }
    
    p {
      margin: 16px 0;
      color: #606266;
    }
    
    .conflict-details {
      margin-top: 20px;
      text-align: left;
      
      .conflict-item {
        display: flex;
        justify-content: space-between;
        padding: 8px 16px;
        background: #f5f7fa;
        border-radius: 4px;
        margin-bottom: 8px;
        
        .local {
          color: #909399;
        }
        
        .server {
          color: #409EFF;
          font-weight: 600;
        }
      }
    }
  }
}
</style>
