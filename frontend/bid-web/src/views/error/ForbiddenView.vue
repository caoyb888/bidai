<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goHome(): void {
  router.push('/')
}

function goBack(): void {
  router.back()
}
</script>

<template>
  <div class="forbidden-container">
    <div class="forbidden-content">
      <div class="forbidden-icon">
        <el-icon :size="120" color="#f56c6c"><WarningFilled /></el-icon>
      </div>
      <h1 class="forbidden-code">403</h1>
      <p class="forbidden-title">无权访问</p>
      <p class="forbidden-desc">您没有权限访问该页面，请联系管理员或返回首页。</p>
      <div class="forbidden-actions">
        <el-button type="primary" size="large" @click="goHome">返回首页</el-button>
        <el-button size="large" @click="goBack">返回上一页</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.forbidden-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
}

.forbidden-content {
  text-align: center;
  padding: 40px;
}

.forbidden-icon {
  margin-bottom: 24px;
}

.forbidden-code {
  margin: 0;
  font-size: 72px;
  font-weight: bold;
  color: #f56c6c;
  line-height: 1;
}

.forbidden-title {
  margin: 16px 0 0;
  font-size: 24px;
  color: #303133;
  font-weight: 500;
}

.forbidden-desc {
  margin: 16px 0 32px;
  font-size: 14px;
  color: #909399;
}

.forbidden-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
}
</style>
