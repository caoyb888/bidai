<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { UserFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

/* ============================================================
 * 菜单配置：index 为路由路径，permission 为显示所需权限码
 * ============================================================ */
interface MenuItem {
  index: string
  title: string
  icon: string
  permission?: string
}

const allMenus: MenuItem[] = [
  { index: '/dashboard', title: '首页', icon: 'HomeFilled' },
  { index: '/projects', title: '项目管理', icon: 'Document', permission: 'project:read' },
  { index: '/knowledge', title: '知识库', icon: 'Reading', permission: 'bid:edit' },
  { index: '/reviews', title: '投标审查', icon: 'Check', permission: 'report:read' },
  { index: '/settings', title: '系统设置', icon: 'Setting', permission: 'user:manage' },
]

/** 根据当前用户权限过滤菜单 */
const visibleMenus = computed<MenuItem[]>(() => {
  return allMenus.filter((menu) => {
    if (!menu.permission) return true
    return authStore.hasPermission(menu.permission)
  })
})

/** 当前激活的菜单项 */
const activeMenu = computed(() => route.path)

/** 用户显示名称 */
const displayName = computed(() => authStore.user?.realName || authStore.user?.username || '用户')

/** 用户角色中文映射（取第一个角色） */
const roleLabel = computed(() => {
  const roleMap: Record<string, string> = {
    SYS_ADMIN: '超级管理员',
    COMP_ADMIN: '公司管理员',
    PROJECT_MGR: '项目经理',
    BID_STAFF: '投标专员',
    APPROVER: '审批人',
    READER: '只读查阅',
  }
  const firstRole = authStore.user?.roles?.[0]
  return firstRole ? roleMap[firstRole] || firstRole : ''
})

const isCollapse = ref(false)

function handleMenuSelect(index: string): void {
  router.push(index)
}

async function handleLogout(): Promise<void> {
  await authStore.logout()
  router.push('/login')
}
</script>

<template>
  <el-container class="main-layout">
    <!-- 顶部 Header -->
    <el-header class="main-header">
      <div class="header-left">
        <el-icon class="logo-icon"><Collection /></el-icon>
        <span class="system-title">AI 智能投标系统</span>
      </div>
      <div class="header-right">
        <el-dropdown trigger="click">
          <div class="user-info">
            <el-avatar :size="32" :icon="UserFilled" class="user-avatar" />
            <div class="user-meta">
              <span class="user-name">{{ displayName }}</span>
              <span v-if="roleLabel" class="user-role">{{ roleLabel }}</span>
            </div>
            <el-icon class="dropdown-icon"><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>
                <span class="dropdown-user">{{ displayName }}</span>
              </el-dropdown-item>
              <el-dropdown-item v-if="roleLabel" disabled>
                <span class="dropdown-role">{{ roleLabel }}</span>
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <el-container class="main-body">
      <!-- 左侧导航 -->
      <el-aside :width="isCollapse ? '64px' : '220px'" class="main-aside">
        <el-menu
          :default-active="activeMenu"
          :collapse="isCollapse"
          :collapse-transition="true"
          class="main-menu"
          @select="handleMenuSelect"
        >
          <el-menu-item v-for="menu in visibleMenus" :key="menu.index" :index="menu.index">
            <el-icon>
              <component :is="menu.icon" />
            </el-icon>
            <template #title>{{ menu.title }}</template>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 主内容区 -->
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.main-layout {
  height: 100vh;
}

.main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #409eff;
  color: #fff;
  padding: 0 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  font-size: 28px;
}

.system-title {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 1px;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.user-info:hover {
  background-color: rgba(255, 255, 255, 0.15);
}

.user-avatar {
  background-color: #fff;
  color: #409eff;
}

.user-meta {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.user-name {
  font-size: 14px;
  font-weight: 500;
}

.user-role {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.85);
}

.dropdown-icon {
  font-size: 12px;
  margin-left: 4px;
}

.dropdown-user {
  font-weight: 500;
  color: #303133;
}

.dropdown-role {
  font-size: 12px;
  color: #909399;
}

.main-body {
  overflow: hidden;
}

.main-aside {
  background-color: #f5f7fa;
  transition: width 0.3s;
}

.main-menu {
  height: 100%;
  border-right: none;
}

.main-content {
  background-color: #fff;
  padding: 20px;
  overflow: auto;
}
</style>
