<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { knowledgeService } from '@/api/knowledge'
import { useAuthStore } from '@/stores/auth'
import KnowledgeStatsPanel from './KnowledgeStatsPanel.vue'
import KnowledgeUploadDialog from './KnowledgeUploadDialog.vue'
import type {
  KnowledgeDocument,
  KnowledgeListParams,
  KnowledgeStatsResponse,
  DocCategory,
} from '@/types'
import {
  DOC_CATEGORY_LABELS,
  DOC_CATEGORY_TYPES,
  INGEST_MODE_LABELS,
} from '@/types'

const authStore = useAuthStore()

/** 权限检查 */
const canManage = computed(() => authStore.hasPermission('knowledge:manage'))

/** 统计看板数据 */
const stats = ref<KnowledgeStatsResponse | null>(null)
const statsLoading = ref(false)

/** 列表数据与加载状态 */
const loading = ref(false)
const documentList = ref<KnowledgeDocument[]>([])
const total = ref(0)

/** 查询参数 */
const queryParams = reactive<KnowledgeListParams>({
  page: 1,
  pageSize: 20,
  doc_category: undefined,
  tags: undefined,
  keyword: '',
})

/** 上传弹窗 */
const uploadDialogVisible = ref(false)

/** 获取统计数据 */
async function fetchStats(): Promise<void> {
  statsLoading.value = true
  try {
    const res = await knowledgeService.getStats()
    stats.value = res
  } catch (err) {
    const error = err as Error
    ElMessage.error(error.message || '获取统计信息失败')
  } finally {
    statsLoading.value = false
  }
}

/** 获取文档列表 */
async function fetchDocuments(): Promise<void> {
  loading.value = true
  try {
    const res = await knowledgeService.listDocuments({
      page: queryParams.page,
      pageSize: queryParams.pageSize,
      doc_category: queryParams.doc_category,
      tags: queryParams.tags,
      keyword: queryParams.keyword || undefined,
    })
    documentList.value = res.items
    total.value = res.total
  } catch (err) {
    const error = err as Error
    ElMessage.error(error.message || '获取文档列表失败')
  } finally {
    loading.value = false
  }
}

/** 搜索 */
function handleSearch(): void {
  queryParams.page = 1
  fetchDocuments()
}

/** 重置筛选 */
function handleReset(): void {
  queryParams.page = 1
  queryParams.pageSize = 20
  queryParams.doc_category = undefined
  queryParams.tags = undefined
  queryParams.keyword = ''
  fetchDocuments()
}

/** 分页变化 */
function handlePageChange(page: number): void {
  queryParams.page = page
  fetchDocuments()
}

function handleSizeChange(size: number): void {
  queryParams.pageSize = size
  queryParams.page = 1
  fetchDocuments()
}

/** 打开上传弹窗 */
function handleUpload(): void {
  uploadDialogVisible.value = true
}

/** 上传成功后刷新 */
function handleUploadSuccess(): void {
  fetchDocuments()
  fetchStats()
}

/** 删除文档 */
async function handleDelete(row: KnowledgeDocument): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档「${row.title}」吗？删除后向量及索引将同步清理（异步）。`,
      '确认删除',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
    )
    await knowledgeService.deleteDocument(row.id)
    ElMessage.success('文档已删除')
    fetchDocuments()
    fetchStats()
  } catch {
    // 用户取消或已处理错误
  }
}

/** 置信度颜色 */
function confidenceColor(confidence: number): string {
  if (confidence >= 0.8) return '#67c23a'
  if (confidence >= 0.6) return '#e6a23c'
  return '#f56c6c'
}

onMounted(() => {
  fetchStats()
  fetchDocuments()
})
</script>

<template>
  <div class="knowledge-page">
    <!-- 统计看板 -->
    <KnowledgeStatsPanel :stats="stats" :loading="statsLoading" />

    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card">
      <el-form :model="queryParams" inline>
        <el-form-item label="关键词">
          <el-input
            v-model="queryParams.keyword"
            placeholder="文档标题"
            clearable
            style="width: 220px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="分类">
          <el-select
            v-model="queryParams.doc_category"
            placeholder="全部分类"
            clearable
            style="width: 160px"
          >
            <el-option
              v-for="(label, value) in DOC_CATEGORY_LABELS"
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
      <el-button v-if="canManage" type="primary" @click="handleUpload">
        <el-icon><Upload /></el-icon>上传文档
      </el-button>
    </div>

    <!-- 数据表格 -->
    <el-card shadow="never">
      <el-table v-loading="loading" :data="documentList" stripe style="width: 100%">
        <el-table-column prop="title" label="文档标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="doc_category" label="分类" width="120">
          <template #default="{ row }">
            <el-tag :type="DOC_CATEGORY_TYPES[row.doc_category as DocCategory]">
              {{ DOC_CATEGORY_LABELS[row.doc_category as DocCategory] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="tags" label="标签" min-width="160">
          <template #default="{ row }">
            <el-tag
              v-for="tag in row.tags.slice(0, 3)"
              :key="tag"
              type="info"
              size="small"
              class="tag-item"
            >
              {{ tag }}
            </el-tag>
            <el-tag v-if="row.tags.length > 3" type="info" size="small">+{{ row.tags.length - 3 }}</el-tag>
            <span v-if="row.tags.length === 0" class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="file_type" label="格式" width="80" />
        <el-table-column prop="page_count" label="页数" width="70" />
        <el-table-column prop="confidence" label="置信度" width="110">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round(row.confidence * 100)"
              :stroke-width="8"
              :color="confidenceColor(row.confidence)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="ingest_mode" label="入库方式" width="110">
          <template #default="{ row }">
            {{ INGEST_MODE_LABELS[row.ingest_mode as keyof typeof INGEST_MODE_LABELS] || row.ingest_mode }}
          </template>
        </el-table-column>
        <el-table-column prop="is_expired" label="状态" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_expired" type="danger" size="small">已过期</el-tag>
            <el-tag v-else type="success" size="small">有效</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canManage" link type="danger" size="small" @click="handleDelete(row)">
              删除
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

    <!-- 上传弹窗 -->
    <KnowledgeUploadDialog v-model:visible="uploadDialogVisible" @success="handleUploadSuccess" />
  </div>
</template>

<style scoped>
.knowledge-page {
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

.tag-item {
  margin-right: 4px;
}

.text-muted {
  color: #909399;
}
</style>
