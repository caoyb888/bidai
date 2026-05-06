<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const welcomeText = computed(() => {
  const name = authStore.user?.realName || authStore.user?.username || '用户'
  const hour = new Date().getHours()
  const greet = hour < 12 ? '早上好' : hour < 18 ? '下午好' : '晚上好'
  return `${greet}，${name}！欢迎使用 AI 智能投标系统。`
})
</script>

<template>
  <div class="dashboard-page">
    <el-card class="welcome-card" shadow="never">
      <h2 class="welcome-title">{{ welcomeText }}</h2>
      <p class="welcome-desc">
        本系统覆盖投标全生命周期，提供招标文件解析、AI 协同编写、投标审查、知识库管理等核心能力。
      </p>
    </el-card>

    <el-row :gutter="20" class="feature-row">
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="feature-header">
              <el-icon color="#409eff"><Document /></el-icon>
              <span>项目管理</span>
            </div>
          </template>
          <p class="feature-desc">创建和管理投标项目，跟踪项目进度与状态。</p>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="feature-header">
              <el-icon color="#67c23a"><Reading /></el-icon>
              <span>知识库</span>
            </div>
          </template>
          <p class="feature-desc">统一管理企业资质、业绩、人员等核心素材。</p>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="feature-header">
              <el-icon color="#e6a23c"><Check /></el-icon>
              <span>投标审查</span>
            </div>
          </template>
          <p class="feature-desc">AI 辅助合规审查，降低废标风险。</p>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.welcome-card {
  background: linear-gradient(90deg, #ecf5ff 0%, #f5f7fa 100%);
  border: none;
}

.welcome-title {
  margin: 0 0 12px;
  font-size: 20px;
  color: #303133;
}

.welcome-desc {
  margin: 0;
  font-size: 14px;
  color: #606266;
}

.feature-row {
  margin-top: 8px;
}

.feature-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  font-size: 16px;
}

.feature-desc {
  margin: 0;
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}
</style>
