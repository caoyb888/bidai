<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import type { LoginRequest } from '@/types'

const router = useRouter()
const authStore = useAuthStore()

const form = reactive<LoginRequest>({
  username: '',
  password: '',
})

const formRef = ref<InstanceType<(typeof import('element-plus'))['ElForm']> | null>(null)

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    await authStore.login(form)
    await authStore.fetchUser()
    ElMessage.success('登录成功')
    router.push('/')
  } catch (err) {
    const error = err as Error & { code?: number }
    let msg = error.message || '登录失败'

    switch (error.code) {
      case 20007:
        msg = '账号已被锁定，请联系管理员'
        break
      case 20008:
        msg = '用户名或密码错误'
        break
      case 20002:
        msg = '登录状态已过期，请重新登录'
        break
      case 20001:
        msg = '登录凭证无效，请重新登录'
        break
    }

    ElMessage.error(msg)
  }
}
</script>

<template>
  <div class="login-container">
    <el-card class="login-card" shadow="hover">
      <template #header>
        <h2 class="login-title">AI 智能投标系统</h2>
        <p class="login-subtitle">用户登录</p>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" @keyup.enter="handleLogin">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="login-btn"
            :loading="authStore.loading"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
}

.login-card {
  width: 420px;
}

.login-title {
  margin: 0;
  font-size: 22px;
  text-align: center;
  color: #303133;
}

.login-subtitle {
  margin: 8px 0 0;
  text-align: center;
  color: #909399;
  font-size: 14px;
}

.login-btn {
  width: 100%;
}
</style>
