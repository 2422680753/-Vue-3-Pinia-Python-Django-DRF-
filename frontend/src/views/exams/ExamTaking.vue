<template>
  <div class="exam-taking-container" :class="{ 'fullscreen-mode': isFullscreen }">
    <el-dialog
      v-model="showExamInfo"
      title="考试须知"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      width="600px"
    >
      <div class="exam-rules">
        <h4>考试规则</h4>
        <ul>
          <li>考试时长：{{ exam.duration }} 分钟</li>
          <li>总分：{{ exam.total_score }} 分</li>
          <li>及格分数：{{ exam.pass_score }} 分</li>
          <li v-if="exam.enable_anti_cheating">
            <el-tag type="danger" size="small">本次考试启用防作弊</el-tag>
            <ul style="margin-top: 8px;">
              <li v-if="exam.require_fullscreen">请保持全屏模式</li>
              <li v-if="exam.block_copy_paste">禁止复制粘贴</li>
              <li v-if="exam.max_tab_switches">切出页面最多 {{ exam.max_tab_switches }} 次</li>
            </ul>
          </li>
        </ul>
        
        <h4 style="margin-top: 20px;">注意事项</h4>
        <ul>
          <li>请确保网络连接稳定</li>
          <li>考试开始后不可随意离开</li>
          <li>系统会自动保存答题进度</li>
          <li>时间结束系统会自动提交</li>
        </ul>
      </div>
      
      <el-form v-if="exam.password" style="margin-top: 20px;">
        <el-form-item label="考试密码">
          <el-input
            v-model="examPassword"
            type="password"
            placeholder="请输入考试密码"
            show-password
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button type="primary" @click="startExam">开始考试</el-button>
      </template>
    </el-dialog>
    
    <div v-if="isExamStarted" class="exam-content">
      <div class="exam-header">
        <div class="exam-title">
          <span>{{ exam.title }}</span>
          <el-tag type="warning" v-if="remainingTime <= 300">
            剩余: {{ formatTime(remainingTime) }}
          </el-tag>
        </div>
        
        <div class="exam-timer">
          <el-icon><Timer /></el-icon>
          <span>{{ formatTime(remainingTime) }}</span>
        </div>
        
        <div class="exam-actions">
          <el-button type="primary" @click="submitExam">交卷</el-button>
        </div>
      </div>
      
      <el-row :gutter="20" class="exam-body">
        <el-col :span="18">
          <div class="question-card">
            <div class="question-header">
              <span class="question-number">第 {{ currentQuestionIndex + 1 }} 题</span>
              <span class="question-score">{{ currentQuestion?.score }} 分</span>
              <el-tag v-if="currentQuestion?.question_type === 'single_choice'" type="primary" size="small">单选题</el-tag>
              <el-tag v-else-if="currentQuestion?.question_type === 'multiple_choice'" type="success" size="small">多选题</el-tag>
              <el-tag v-else-if="currentQuestion?.question_type === 'true_false'" type="warning" size="small">判断题</el-tag>
              <el-tag v-else-if="currentQuestion?.question_type === 'fill_blank'" type="info" size="small">填空题</el-tag>
              <el-tag v-else-if="currentQuestion?.question_type === 'essay'" type="danger" size="small">简答题</el-tag>
            </div>
            
            <div class="question-content">
              <div class="question-text" v-html="currentQuestion?.content"></div>
              
              <div v-if="currentQuestion?.question_type === 'single_choice'" class="options-list">
                <el-radio-group v-model="selectedOptions">
                  <el-radio
                    v-for="option in currentQuestion?.options"
                    :key="option.key"
                    :label="option.key"
                    class="option-item"
                  >
                    <span class="option-key">{{ option.key }}.</span>
                    <span class="option-text">{{ option.value }}</span>
                  </el-radio>
                </el-radio-group>
              </div>
              
              <div v-else-if="currentQuestion?.question_type === 'multiple_choice'" class="options-list">
                <el-checkbox-group v-model="selectedOptions">
                  <el-checkbox
                    v-for="option in currentQuestion?.options"
                    :key="option.key"
                    :label="option.key"
                    class="option-item"
                  >
                    <span class="option-key">{{ option.key }}.</span>
                    <span class="option-text">{{ option.value }}</span>
                  </el-checkbox>
                </el-checkbox-group>
              </div>
              
              <div v-else-if="currentQuestion?.question_type === 'true_false'" class="options-list">
                <el-radio-group v-model="selectedOptions">
                  <el-radio label="true" class="option-item">正确</el-radio>
                  <el-radio label="false" class="option-item">错误</el-radio>
                </el-radio-group>
              </div>
              
              <div v-else-if="currentQuestion?.question_type === 'fill_blank'" class="fill-blank-area">
                <div v-for="(blank, index) in currentQuestion?.blanks" :key="index" class="blank-item">
                  <span>{{ index + 1 }}. </span>
                  <el-input
                    v-model="fillBlanks[index]"
                    placeholder="请输入答案"
                    style="width: 300px;"
                  />
                </div>
              </div>
              
              <div v-else-if="currentQuestion?.question_type === 'essay'" class="essay-area">
                <el-input
                  v-model="essayAnswer"
                  type="textarea"
                  :rows="8"
                  placeholder="请输入你的答案..."
                />
              </div>
            </div>
            
            <div class="question-footer">
              <el-button @click="prevQuestion" :disabled="currentQuestionIndex === 0">
                上一题
              </el-button>
              <el-button type="primary" @click="nextQuestion">
                下一题
              </el-button>
              <div class="flag-btn">
                <el-checkbox v-model="isCurrentFlagged" label="标记本题"></el-checkbox>
              </div>
            </div>
          </div>
        </el-col>
        
        <el-col :span="6">
          <div class="answer-card">
            <div class="card-header">答题卡</div>
            
            <div class="card-stats">
              <span>已答: <el-tag type="success" size="small">{{ answeredCount }}</el-tag></span>
              <span>未答: <el-tag type="info" size="small">{{ unansweredCount }}</el-tag></span>
              <span>标记: <el-tag type="warning" size="small">{{ flaggedCount }}</el-tag></span>
            </div>
            
            <div class="card-questions">
              <div 
                v-for="(question, index) in examQuestions" 
                :key="question.id"
                class="question-dot"
                :class="{
                  active: index === currentQuestionIndex,
                  answered: isQuestionAnswered(index),
                  flagged: isQuestionFlagged(index)
                }"
                @click="goToQuestion(index)"
              >
                {{ index + 1 }}
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
      
      <el-dialog
        v-model="showSubmitConfirm"
        title="确认交卷"
        width="400px"
      >
        <div class="submit-info">
          <p>您已完成 <strong>{{ answeredCount }}</strong> / <strong>{{ examQuestions.length }}</strong> 道题目</p>
          <p v-if="unansweredCount > 0">
            还有 <el-tag type="danger" size="small">{{ unansweredCount }}</el-tag> 道题目未作答
          </p>
          <p>确认要提交试卷吗？</p>
        </div>
        
        <template #footer>
          <el-button @click="showSubmitConfirm = false">继续答题</el-button>
          <el-button type="primary" @click="confirmSubmit">确认交卷</el-button>
        </template>
      </el-dialog>
      
      <el-dialog
        v-model="showTimeUp"
        title="考试时间已到"
        width="400px"
        :close-on-click-modal="false"
        :close-on-press-escape="false"
      >
        <div class="time-up-info">
          <el-icon :size="48" color="#E6A23C"><Timer /></el-icon>
          <p>考试时间已到，系统将自动提交您的试卷</p>
        </div>
      </el-dialog>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { examApi, Exam, ExamAttempt, ExamQuestion } from '@/api/exams'
import { examAntiCheating } from '@/utils/examAntiCheating'
import { examMonitoringSocket } from '@/utils/websocket'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()

const examId = computed(() => parseInt(route.params.examId as string))

const exam = ref<Exam>()
const examQuestions = ref<ExamQuestion[]>([])
const examAttempt = ref<ExamAttempt>()

const showExamInfo = ref(true)
const isExamStarted = ref(false)
const examPassword = ref('')

const currentQuestionIndex = ref(0)
const selectedOptions = ref<string[]>([])
const fillBlanks = ref<string[]>([])
const essayAnswer = ref('')
const isCurrentFlagged = ref(false)

const remainingTime = ref(0)
let timer: number | null = null

const answers = reactive<Record<number, any>>({})
const flaggedQuestions = ref<Set<number>>(new Set())
const isFullscreen = ref(false)

const showSubmitConfirm = ref(false)
const showTimeUp = ref(false)

const currentQuestion = computed(() => {
  return examQuestions.value[currentQuestionIndex.value]
})

const answeredCount = computed(() => {
  return Object.keys(answers).length
})

const unansweredCount = computed(() => {
  return examQuestions.value.length - answeredCount.value
})

const flaggedCount = computed(() => {
  return flaggedQuestions.value.size
})

const formatTime = (seconds: number) => {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

const isQuestionAnswered = (index: number) => {
  const question = examQuestions.value[index]
  return question && answers[question.id] !== undefined
}

const isQuestionFlagged = (index: number) => {
  const question = examQuestions.value[index]
  return question && flaggedQuestions.value.has(question.id)
}

const loadExamData = async () => {
  try {
    const examData = await examApi.getExamDetail(examId.value)
    exam.value = examData
    
    remainingTime.value = examData.duration * 60
  } catch (error) {
    console.error('Failed to load exam:', error)
    ElMessage.error('加载考试信息失败')
  }
}

const startExam = async () => {
  try {
    const data: any = {}
    if (exam.value?.password) {
      if (!examPassword.value) {
        ElMessage.warning('请输入考试密码')
        return
      }
      data.password = examPassword.value
    }
    
    const attempt = await examApi.startExam(examId.value, data)
    examAttempt.value = attempt
    examQuestions.value = attempt.questions || []
    
    isFullscreen.value = exam.value?.require_fullscreen || false
    
    if (isFullscreen.value) {
      try {
        await document.documentElement.requestFullscreen()
      } catch (e) {
        console.warn('无法进入全屏模式')
      }
    }
    
    if (exam.value?.enable_anti_cheating) {
      examAntiCheating.init(attempt.id, {
        maxTabSwitches: exam.value.max_tab_switches || 5,
        maxIdleTime: exam.value.max_idle_time || 300,
        requireFullscreen: exam.value.require_fullscreen || false,
        blockCopyPaste: exam.value.block_copy_paste || false,
        blockRightClick: exam.value.block_right_click || false,
        enableFaceVerification: exam.value.enable_face_verification || false,
        verifyInterval: exam.value.verify_interval || 300
      })
      
      connectExamWebSocket()
    }
    
    startTimer()
    isExamStarted.value = true
    showExamInfo.value = false
    
    ElMessage.success('考试开始！')
  } catch (error: any) {
    console.error('Failed to start exam:', error)
    ElMessage.error(error.response?.data?.error || '开始考试失败')
  }
}

const connectExamWebSocket = () => {
  if (!examAttempt.value) return
  
  examMonitoringSocket.connect(`/ws/exam/monitoring/${examAttempt.value.id}/`, {
    onMessage: (data: any) => {
      console.log('Exam WebSocket message:', data)
      
      if (data.type === 'force_submit') {
        ElMessage.error({
          message: '系统检测到作弊行为，考试已被强制提交',
          duration: 0
        })
        handleForcedSubmit(data.reason)
      }
      
      if (data.type === 'warning') {
        ElMessage.warning(data.message)
      }
    }
  })
}

const startTimer = () => {
  timer = window.setInterval(() => {
    if (remainingTime.value > 0) {
      remainingTime.value--
      
      if (remainingTime.value === 300) {
        ElMessage.warning('距离考试结束还有5分钟！')
      }
      
      if (remainingTime.value === 60) {
        ElMessage.warning('距离考试结束还有1分钟！')
      }
      
      if (remainingTime.value <= 0) {
        handleTimeUp()
      }
    }
  }, 1000)
}

const handleTimeUp = () => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  
  showTimeUp.value = true
  
  setTimeout(() => {
    confirmSubmit(true)
  }, 3000)
}

const handleForcedSubmit = (reason: string) => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  
  confirmSubmit(false, reason)
}

const saveCurrentAnswer = () => {
  if (!currentQuestion.value) return
  
  const questionId = currentQuestion.value.id
  const questionType = currentQuestion.value.question_type
  
  let answerData: any = {}
  
  if (questionType === 'single_choice') {
    answerData = {
      answer_choice: selectedOptions.value.length > 0 ? [selectedOptions.value[0]] : [],
      is_skipped: selectedOptions.value.length === 0
    }
  } else if (questionType === 'multiple_choice') {
    answerData = {
      answer_choice: selectedOptions.value,
      is_skipped: selectedOptions.value.length === 0
    }
  } else if (questionType === 'true_false') {
    answerData = {
      answer_text: selectedOptions.value.length > 0 ? selectedOptions.value[0] : '',
      is_skipped: selectedOptions.value.length === 0
    }
  } else if (questionType === 'fill_blank') {
    answerData = {
      answer_text: JSON.stringify(fillBlanks.value),
      is_skipped: fillBlanks.value.every(b => !b)
    }
  } else if (questionType === 'essay') {
    answerData = {
      answer_text: essayAnswer.value,
      is_skipped: !essayAnswer.value
    }
  }
  
  answers[questionId] = {
    ...answerData,
    is_flagged: isCurrentFlagged.value
  }
  
  if (isCurrentFlagged.value) {
    flaggedQuestions.value.add(questionId)
  } else {
    flaggedQuestions.value.delete(questionId)
  }
  
  if (examAttempt.value && exam.value?.enable_anti_cheating) {
    examAntiCheating.sendAnswerUpdate(questionId, answerData)
  }
}

const loadAnswer = () => {
  if (!currentQuestion.value) return
  
  const questionId = currentQuestion.value.id
  const savedAnswer = answers[questionId]
  
  if (savedAnswer) {
    if (savedAnswer.answer_choice) {
      selectedOptions.value = [...savedAnswer.answer_choice]
    } else {
      selectedOptions.value = []
    }
    
    if (savedAnswer.answer_text && currentQuestion.value.question_type === 'fill_blank') {
      try {
        fillBlanks.value = JSON.parse(savedAnswer.answer_text)
      } catch {
        fillBlanks.value = []
      }
    } else if (savedAnswer.answer_text && currentQuestion.value.question_type === 'essay') {
      essayAnswer.value = savedAnswer.answer_text
    } else {
      fillBlanks.value = []
      essayAnswer.value = ''
    }
    
    isCurrentFlagged.value = !!savedAnswer.is_flagged
  } else {
    selectedOptions.value = []
    fillBlanks.value = []
    essayAnswer.value = ''
    isCurrentFlagged.value = false
  }
}

const goToQuestion = (index: number) => {
  saveCurrentAnswer()
  currentQuestionIndex.value = index
  loadAnswer()
}

const prevQuestion = () => {
  if (currentQuestionIndex.value > 0) {
    goToQuestion(currentQuestionIndex.value - 1)
  }
}

const nextQuestion = () => {
  saveCurrentAnswer()
  
  if (currentQuestionIndex.value < examQuestions.value.length - 1) {
    currentQuestionIndex.value++
    loadAnswer()
  } else {
    ElMessage('已到达最后一题')
  }
}

const submitExam = () => {
  saveCurrentAnswer()
  showSubmitConfirm.value = true
}

const confirmSubmit = async (autoSubmit: boolean = false, reason?: string) => {
  try {
    if (examAttempt.value) {
      const submitData: any = {
        answers: Object.entries(answers).map(([questionId, data]) => ({
          question_id: parseInt(questionId),
          ...data
        })),
        is_auto_submit: autoSubmit
      }
      
      if (reason) {
        submitData.force_submit_reason = reason
      }
      
      await examApi.submitExam(examAttempt.value.id, submitData)
    }
    
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    
    examAntiCheating.stop()
    examMonitoringSocket.disconnect()
    
    ElMessage.success(autoSubmit ? '考试已自动提交' : '提交成功！')
    
    if (examAttempt.value) {
      router.push(`/exams/${examAttempt.value.exam}/result/${examAttempt.value.id}`)
    } else {
      router.push('/exams')
    }
  } catch (error) {
    console.error('Failed to submit exam:', error)
    ElMessage.error('提交失败，请重试')
  }
}

watch(currentQuestionIndex, () => {
  loadAnswer()
})

watch(isCurrentFlagged, (val) => {
  if (currentQuestion.value) {
    if (val) {
      flaggedQuestions.value.add(currentQuestion.value.id)
    } else {
      flaggedQuestions.value.delete(currentQuestion.value.id)
    }
  }
})

onMounted(() => {
  loadExamData()
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
  examAntiCheating.stop()
  examMonitoringSocket.disconnect()
})
</script>

<style scoped lang="scss">
.exam-taking-container {
  background: #f0f2f5;
  min-height: 100vh;
  
  &.fullscreen-mode {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 9999;
    
    .exam-content {
      height: 100vh;
    }
  }
  
  .exam-rules {
    h4 {
      font-size: 16px;
      font-weight: 600;
      margin: 0 0 12px;
    }
    
    ul {
      margin: 0;
      padding-left: 20px;
      
      li {
        margin-bottom: 8px;
        color: #606266;
      }
    }
  }
  
  .exam-content {
    display: flex;
    flex-direction: column;
    height: 100vh;
    
    .exam-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      height: 60px;
      background: #fff;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      z-index: 10;
      
      .exam-title {
        font-size: 18px;
        font-weight: 600;
        
        .el-tag {
          margin-left: 12px;
        }
      }
      
      .exam-timer {
        display: flex;
        align-items: center;
        font-size: 24px;
        font-weight: bold;
        color: #409EFF;
        
        .el-icon {
          margin-right: 8px;
        }
      }
    }
    
    .exam-body {
      flex: 1;
      padding: 20px;
      overflow-y: auto;
      
      .question-card {
        background: #fff;
        border-radius: 8px;
        padding: 24px;
        
        .question-header {
          display: flex;
          align-items: center;
          margin-bottom: 20px;
          padding-bottom: 16px;
          border-bottom: 1px solid #ebeef5;
          
          .question-number {
            font-size: 16px;
            font-weight: 600;
          }
          
          .question-score {
            margin-left: 16px;
            color: #E6A23C;
          }
          
          .el-tag {
            margin-left: 8px;
          }
        }
        
        .question-content {
          .question-text {
            font-size: 16px;
            line-height: 1.8;
            margin-bottom: 24px;
          }
          
          .options-list {
            .option-item {
              display: flex;
              align-items: flex-start;
              padding: 12px 16px;
              margin-bottom: 8px;
              border: 1px solid #dcdfe6;
              border-radius: 4px;
              transition: all 0.3s;
              
              &:hover {
                border-color: #409EFF;
              }
              
              :deep(.el-radio),
              :deep(.el-checkbox) {
                margin-right: 12px;
              }
              
              .option-key {
                font-weight: 600;
                margin-right: 8px;
              }
              
              .option-text {
                color: #606266;
              }
            }
          }
          
          .fill-blank-area {
            .blank-item {
              display: flex;
              align-items: center;
              margin-bottom: 12px;
            }
          }
          
          .essay-area {
            :deep(.el-textarea) {
              font-size: 14px;
            }
          }
        }
        
        .question-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-top: 32px;
          padding-top: 16px;
          border-top: 1px solid #ebeef5;
          
          .flag-btn {
            :deep(.el-checkbox) {
              color: #E6A23C;
            }
          }
        }
      }
      
      .answer-card {
        background: #fff;
        border-radius: 8px;
        padding: 16px;
        
        .card-header {
          font-size: 16px;
          font-weight: 600;
          padding-bottom: 12px;
          border-bottom: 1px solid #ebeef5;
          margin-bottom: 16px;
        }
        
        .card-stats {
          display: flex;
          justify-content: space-around;
          margin-bottom: 16px;
          
          span {
            font-size: 13px;
            color: #606266;
          }
        }
        
        .card-questions {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          
          .question-dot {
            width: 36px;
            height: 36px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid #dcdfe6;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
            
            &:hover {
              border-color: #409EFF;
              color: #409EFF;
            }
            
            &.active {
              background: #409EFF;
              border-color: #409EFF;
              color: #fff;
            }
            
            &.answered {
              background: #f0f9eb;
              border-color: #67C23A;
              color: #67C23A;
              
              &.active {
                background: #67C23A;
                color: #fff;
              }
            }
            
            &.flagged {
              position: relative;
              
              &::after {
                content: '';
                position: absolute;
                top: -2px;
                right: -2px;
                width: 8px;
                height: 8px;
                background: #E6A23C;
                border-radius: 50%;
              }
            }
          }
        }
      }
    }
  }
  
  .submit-info,
  .time-up-info {
    text-align: center;
    
    p {
      margin: 12px 0;
      color: #606266;
    }
    
    .el-icon {
      margin-bottom: 16px;
    }
  }
}
</style>
