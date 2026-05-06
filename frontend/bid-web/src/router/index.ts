import { createRouter, createWebHistory } from 'vue-router'
import { getAccessToken } from '@/utils/token'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'
import HomeView from '@/views/HomeView.vue'
import MainLayout from '@/layouts/MainLayout.vue'
import ForbiddenView from '@/views/error/ForbiddenView.vue'
import PlaceholderView from '@/views/PlaceholderView.vue'
import ProjectListView from '@/views/project/ProjectListView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: LoginView,
      meta: { public: true },
    },
    {
      path: '/403',
      name: 'Forbidden',
      component: ForbiddenView,
      meta: { public: true },
    },
    {
      path: '/',
      component: MainLayout,
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: HomeView,
          meta: { title: '首页' },
        },
        {
          path: 'projects',
          name: 'Projects',
          component: ProjectListView,
          meta: { title: '项目管理', permission: 'project:read' },
        },
        {
          path: 'knowledge',
          name: 'Knowledge',
          component: PlaceholderView,
          meta: { title: '知识库', permission: 'bid:edit' },
        },
        {
          path: 'reviews',
          name: 'Reviews',
          component: PlaceholderView,
          meta: { title: '投标审查', permission: 'report:read' },
        },
        {
          path: 'settings',
          name: 'Settings',
          component: PlaceholderView,
          meta: { title: '系统设置', permission: 'user:manage' },
        },
      ],
    },
  ],
})

/* ============================================================
 * 全局路由守卫：认证 + 权限校验
 * ============================================================ */
router.beforeEach(async (to, _from, next) => {
  const hasToken = !!getAccessToken()

  // 1. 白名单路由（登录页、403 页等）直接放行
  if (to.meta.public) {
    // 已登录用户访问登录页 → 跳转到首页
    if (hasToken && to.path === '/login') {
      return next('/')
    }
    return next()
  }

  // 2. 未登录 → 强制跳转登录页
  if (!hasToken) {
    return next('/login')
  }

  // 3. 已登录但 Pinia 中无用户信息 → 拉取当前用户
  const authStore = useAuthStore()
  if (!authStore.user) {
    await authStore.fetchUser()
    // fetchUser 内部已捕获异常；若仍无用户信息，说明 Token 已失效
    if (!authStore.user) {
      authStore.clearAuthState()
      return next('/login')
    }
  }

  // 4. 校验路由权限
  const requiredPermission = to.meta.permission
  if (requiredPermission && !authStore.hasPermission(requiredPermission)) {
    return next('/403')
  }

  next()
})

export default router
