import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import { createPinia } from 'pinia'
import router from '@/router'
import App from '@/App.vue'
import { setUnauthorizedHandler } from '@/api'
import { useAuthStore } from '@/stores/auth'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(ElementPlus)
app.use(createPinia())
app.use(router)

// 设置未授权处理器：Token 刷新失败或 refresh_token 失效时跳转登录页
setUnauthorizedHandler(() => {
  const authStore = useAuthStore()
  authStore.clearAuthState()
  router.push('/login')
})

app.mount('#app')
