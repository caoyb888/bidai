<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { projectService } from '@/api/project'
import { useAuthStore } from '@/stores/auth'
import ProjectFormDialog from './ProjectFormDialog.vue'
import type { ProjectBrief, ProjectDetail, ProjectListParams, ProjectStatus } from '@/types/project'
import { PROJECT_STATUS_LABELS, PROJECT_STATUS_TYPES } from '@/types/project'

const authStore = useAuthStore()

/** 权限检查 */
const canCreate = computed(() => authStore.hasPermission('project:create'))
const canEdit = computed(() => authStore.hasPermission('project:create'))

/** 列表数据与加载状态 */
const loading = ref(false)
const projectList = ref<ProjectBrief[]>([])
const total = ref(0)

/** 查询参数 */
const queryParams = reactive<ProjectListParams>({
  page: 1,
  pageSize: 20,
  status: undefined,
  keyword: '',
})

/** 弹窗状态 */
const dialogVisible = ref(false)
const editingProject = ref<ProjectDetail | null>(null)

/** 获取列表 */
async function fetchProjects(): Promise<void> {
  loading.value = true
  try {
    const res = await projectService.listProjects({
      page: queryParams.page,
      pageSize: queryParams.pageSize,
      status: queryParams.status,
      keyword: queryParams.keyword || undefined,
    })
    projectList.value = res.items
    total.value = res.total
  } catch (err) {
    const error = err as Error
    ElMessage.error(error.message || '获取项目列表失败')
  } finally {
    loading.value = false
  }
}

/** 搜索 */
function handleSearch(): void {
  queryParams.page = 1
  fetchProjects()
}

/** 重置筛选 */
function handleReset(): void {
  queryParams.page = 1
  queryParams.pageSize = 20
  queryParams.status = undefined
  queryParams.keyword = ''
  fetchProjects()
}

/** 分页变化 */
function handlePageChange(page: number): void {
  queryParams.page = page
  fetchProjects()
}

function handleSizeChange(size: number): void {
  queryParams.pageSize = size
  queryParams.page = 1
  fetchProjects()
}

/** 打开创建弹窗 */
function handleCreate(): void {
  editingProject.value = null
  dialogVisible.value = true
}

/** 打开编辑弹窗 */
async function handleEdit(row: ProjectBrief): Promise<void> {
  try {
    loading.value = true
    const detail = await projectService.getProject(row.id)
    editingProject.value = detail
    dialogVisible.value = true
  } catch (err) {
    const error = err as Error
    ElMessage.error(error.message || '获取项目详情失败')
  } finally {
    loading.value = false
  }
}

/** 归档项目 */
async function handleArchive(row: ProjectBrief): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定要归档项目「${row.name}」吗？归档后可在管理后台恢复。`,
      '确认归档',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
    )
    await projectService.deleteProject(row.id)
    ElMessage.success('项目已归档')
    fetchProjects()
  } catch {
    // 用户取消或已处理错误
  }
}

/** 弹窗操作成功后刷新列表 */
function handleDialogSuccess(): void {
  fetchProjects()
}

onMounted(() => {
  fetchProjects()
})
</script>

<template>
  <div class="project-list-page">
    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card">
      <el-form :model="queryParams" inline>
        <el-form-item label="关键词">
          <el-input
            v-model="queryParams.keyword"
            placeholder="项目名称 / 客户"
            clearable
            style="width: 220px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="queryParams.status"
            placeholder="全部状态"
            clearable
            style="width: 160px"
          >
            <el-option
              v-for="(label, value) in PROJECT_STATUS_LABELS"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>查询
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 操作栏 -->
    <div class="toolbar">
      <el-button v-if="canCreate" type="primary" @click="handleCreate">
        <el-icon><Plus /></el-icon>创建项目
      </el-button>
    </div>

    <!-- 数据表格 -->
    <el-card shadow="never">
      <el-table v-loading="loading" :data="projectList" stripe style="width: 100%">
        <el-table-column prop="name" label="项目名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="client" label="客户名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="PROJECT_STATUS_TYPES[row.status as ProjectStatus]">
              {{ PROJECT_STATUS_LABELS[row.status as ProjectStatus] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="tenderDate" label="开标日期" width="120" />
        <el-table-column prop="industry" label="行业" width="120" show-overflow-tooltip />
        <el-table-column prop="budgetAmount" label="预算金额" width="140">
          <template #default="{ row }">
            <span v-if="row.budgetAmount">¥ {{ row.budgetAmount }}</span>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="winRateScore" label="胜率" width="100">
          <template #default="{ row }">
            <el-progress
              v-if="row.winRateScore != null"
              :percentage="Math.round(row.winRateScore)"
              :stroke-width="10"
              :color="{ '0%': '#f56c6c', '50%': '#e6a23c', '100%': '#67c23a' }"
            />
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canEdit" link type="primary" size="small" @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button v-if="canEdit" link type="danger" size="small" @click="handleArchive(row)">
              归档
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <!-- 创建/编辑弹窗 -->
    <ProjectFormDialog
      v-model:visible="dialogVisible"
      :project="editingProject"
      @success="handleDialogSuccess"
    />
  </div>
</template>

<style scoped>
.project-list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card {
  padding-bottom: 0;
}

.filter-card :deep(.el-card__body) {
  padding-bottom: 12px;
}

.toolbar {
  display: flex;
  justify-content: flex-end;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.text-muted {
  color: #909399;
}
</style>
