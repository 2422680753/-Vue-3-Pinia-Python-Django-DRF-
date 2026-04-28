<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <el-icon :size="48" color="#409EFF"><VideoCamera /></el-icon>
        <h1>在线教育学习平台</h1>
        <p class="subtitle">智慧学习，成就未来</p>
      </div>
      
      <el-form 
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        class="login-form"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="username">
          <el-input 
            v-model="loginForm.username"
            placeholder="请输入用户名"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input 
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            prefix-icon="Lock"
            size="large"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        
        <el-form-item>
          <el-checkbox v-model="rememberMe">记住我</el-checkbox>
          <el-link type="primary" class="forget-password">忘记密码？</el-link>
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            size="large" 
            :loading="loading"
            @click="handleLogin"
            class="login-btn"
          >
            登 录
          </el-button>
        </el-form-item>
        
        <el-form-item class="register-link">
          <span>还没有账号？</span>
          <el-link type="primary" @click="$router.push('/register')">立即注册</el-link>
        </el-form-item>
      </el-form>
      
      <div class="quick-login">
        <div class="divider">
          <span>快捷登录</span>
        </div>
        <div class="quick-login-btns">
          <el-button type="info" circle>
            <el-icon><ChatDotRound /></el-icon>
          </el-button>
          <el-button type="primary" circle>
            <el-icon><Phone /></el-icon>
          </el-button>
          <el-button type="success" circle>
            <el-icon><Message /></el-icon>
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const loginFormRef = ref<FormInstance>()
const loading = ref(false)
const rememberMe = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const loginRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await userStore.login({
          username: loginForm.username,
          password: loginForm.password
        })
        
        ElMessage.success('登录成功！')
        
        const redirect = route.query.redirect as string
        if (redirect) {
          router.push(redirect)
        } else {
          router.push('/dashboard')
        }
      } catch (error: any) {
        console.error('Login error:', error)
        ElMessage.error(error.response?.data?.detail || '登录失败，请检查用户名和密码')
      } finally {
        loading.value = false
      }
    }
  })
}

onMounted(() => {
  const savedUsername = localStorage.getItem('saved_username')
  if (savedUsername) {
    loginForm.username = savedUsername
    rememberMe.value = true
  }
})
</script>

<style scoped lang="scss">
.login-container {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-box {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border-radius: 12px;
  padding: 40px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
  
  h1 {
    margin: 16px 0 8px;
    font-size: 24px;
    color: #303133;
  }
  
  .subtitle {
    color: #909399;
    font-size: 14px;
  }
}

.login-form {
  .el-input {
    height: 44px;
  }
  
  .el-form-item {
    margin-bottom: 24px;
  }
  
  .forget-password {
    float: right;
  }
  
  .login-btn {
    width: 100%;
    height: 44px;
    font-size: 16px;
  }
  
  .register-link {
    text-align: center;
    color: #909399;
    font-size: 14px;
  }
}

.quick-login {
  margin-top: 32px;
  
  .divider {
    position: relative;
    text-align: center;
    margin-bottom: 20px;
    
    &::before {
      content: '';
      position: absolute;
      top: 50%;
      left: 0;
      right: 0;
      height: 1px;
      background: #e4e7ed;
    }
    
    span {
      position: relative;
      background: #fff;
      padding: 0 16px;
      color: #909399;
      font-size: 14px;
    }
  }
  
  .quick-login-btns {
    display: flex;
    justify-content: center;
    gap: 16px;
  }
}
</style>
