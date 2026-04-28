<template>
  <el-container class="layout-container">
    <el-aside :width="isCollapse ? '64px' : '240px'" class="layout-aside">
      <div class="logo">
        <el-icon v-if="isCollapse" :size="32"><VideoCamera /></el-icon>
        <template v-else>
          <el-icon :size="24"><VideoCamera /></el-icon>
          <span class="logo-text">在线教育平台</span>
        </template>
      </div>
      
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>学习中心</template>
        </el-menu-item>
        
        <el-menu-item index="/courses">
          <el-icon><Reading /></el-icon>
          <template #title>课程学习</template>
        </el-menu-item>
        
        <el-menu-item index="/assignments">
          <el-icon><Document /></el-icon>
          <template #title>作业管理</template>
        </el-menu-item>
        
        <el-menu-item index="/exams">
          <el-icon><Edit /></el-icon>
          <template #title>在线考试</template>
        </el-menu-item>
        
        <el-menu-item index="/classes">
          <el-icon><User /></el-icon>
          <template #title>我的班级</template>
        </el-menu-item>
        
        <el-menu-item index="/analytics">
          <el-icon><TrendCharts /></el-icon>
          <template #title>学情分析</template>
        </el-menu-item>
        
        <el-sub-menu v-if="isTeacher || isAdmin" index="teacher">
          <template #title>
            <el-icon><Tools /></el-icon>
            <span>教学管理</span>
          </template>
          <el-menu-item index="/teacher/courses">课程管理</el-menu-item>
          <el-menu-item index="/teacher/classes">班级管理</el-menu-item>
          <el-menu-item index="/teacher/assignments">作业管理</el-menu-item>
          <el-menu-item index="/teacher/exams">考试管理</el-menu-item>
          <el-menu-item index="/teacher/analytics">教学分析</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    
    <el-container>
      <el-header class="layout-header">
        <div class="header-left">
          <el-icon 
            class="collapse-btn" 
            @click="isCollapse = !isCollapse"
          >
            <component :is="isCollapse ? 'Expand' : 'Fold'" />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentTitle">{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        
        <div class="header-right">
          <el-dropdown trigger="click" @command="handleCommand">
            <div class="user-info">
              <el-avatar :size="32" :src="userStore.userInfo?.avatar || ''">
                {{ userStore.userInfo?.real_name?.charAt(0) || userStore.userInfo?.username?.charAt(0) || 'U' }}
              </el-avatar>
              <span class="user-name">
                {{ userStore.userInfo?.real_name || userStore.userInfo?.username }}
              </span>
              <el-tag v-if="isAdmin" type="danger" size="small">管理员</el-tag>
              <el-tag v-else-if="isTeacher" type="primary" size="small">教师</el-tag>
              <el-tag v-else type="success" size="small">学生</el-tag>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>
                  个人中心
                </el-dropdown-item>
                <el-dropdown-item command="settings">
                  <el-icon><Setting /></el-icon>
                  设置
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <el-main class="layout-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isCollapse = ref(false)
const isTeacher = computed(() => userStore.isTeacher)
const isAdmin = computed(() => userStore.isAdmin)
const activeMenu = computed(() => route.path)

const currentTitle = computed(() => {
  const matched = route.matched
  if (matched.length > 1) {
    const title = matched[matched.length - 1].meta?.title
    return title
  }
  return null
})

const handleCommand = (command: string) => {
  switch (command) {
    case 'profile':
      router.push('/profile')
      break
    case 'settings':
      router.push('/profile')
      break
    case 'logout':
      userStore.logout()
      router.push('/login')
      break
  }
}
</script>

<style scoped lang="scss">
.layout-container {
  height: 100vh;
}

.layout-aside {
  background-color: #304156;
  transition: width 0.3s;
  
  .logo {
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 16px;
    color: #fff;
    font-size: 18px;
    font-weight: bold;
    border-bottom: 1px solid #3a4a5b;
    
    .logo-text {
      margin-left: 8px;
    }
  }
  
  .el-menu {
    border-right: none;
  }
}

.layout-header {
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  
  .header-left {
    display: flex;
    align-items: center;
    
    .collapse-btn {
      font-size: 20px;
      cursor: pointer;
      margin-right: 16px;
      transition: color 0.3s;
      
      &:hover {
        color: #409EFF;
      }
    }
  }
  
  .header-right {
    .user-info {
      display: flex;
      align-items: center;
      cursor: pointer;
      
      .user-name {
        margin: 0 8px;
      }
    }
  }
}

.layout-main {
  background-color: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
