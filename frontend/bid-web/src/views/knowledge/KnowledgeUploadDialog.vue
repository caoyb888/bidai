<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { knowledgeService } from '@/api/knowledge'
import type { UploadProgressItem, DocCategory } from '@/types'
import { DOC_CATEGORY_LABELS, TASK_STATUS_LABELS, TASK_STATUS_TYPES } from '@/types'

interface Props {
  visible: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'success'): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

/** 支持的文件类型 */
const ACCEPT_TYPES = '.pdf,.docx,.xlsx,.jpg,.jpeg,.png'
const MAX_FILE_SIZE = 100 * 1024 * 1024 // 100MB

/** 表单数据 */
const selectedCategory = ref<DocCategory>('GENERAL')
const selectedTags = ref<string[]>([])
const tagInput = ref('')

/** 上传进度列表 */
const uploadProgressList = ref<UploadProgressItem[]>([])
const isUploading = ref(false)

/** 轮询定时器 */
const pollTimers = ref<Map<string, number>>(new Map())

/** 分类选项 */
const categoryOptions = computed(() => {
  return (Object.keys(DOC_CATEGORY_LABELS) as DocCategory[]).map((key) => ({
    label: DOC_CATEGORY_LABELS[key],
    value: key,
  }))
})

/** 添加标签 */
function handleAddTag(): void {
  const tag = tagInput.value.trim()
  if (!tag) return
  if (selectedTags.value.includes(tag)) {
    ElMessage.warning('标签已存在')
    return
  }
  selectedTags.value.push(tag)
  tagInput.value = ''
}

/** 移除标签 */
function handleRemoveTag(tag: string): void {
  selectedTags.value = selectedTags.value.filter((t) => t !== tag)
}

/** 处理 el-upload 的 change 事件 */
function handleUploadChange(uploadFile: UploadFile): void {
  const file = uploadFile.raw
  if (!file) return

  if (file.size > MAX_FILE_SIZE) {
    ElMessage.error(`「${file.name}」超过 100MB 限制，无法上传`)
    return
  }

  performUpload(file)
}

/** 执行上传 */
async function performUpload(file: File): Promise<void> {
  isUploading.value = true

  const formData = new FormData()
  formData.append('file', file)
  formData.append('doc_category', selectedCategory.value)
  if (selectedTags.value.length > 0) {
    formData.append('tags', JSON.stringify(selectedTags.value))
  }

  try {
    const res = await knowledgeService.uploadDocument(formData)

    const progressItem: UploadProgressItem = {
      taskId: res.task_id,
      fileName: file.name,
      status: res.status,
      progress: res.status === 'SUCCESS' ? 100 : 0,
      documentId: res.document_id,
      isDuplicate: res.is_duplicate,
    }

    uploadProgressList.value.push(progressItem)

    if (res.is_duplicate) {
      ElMessage.info(`「${file.name}」文件已存在，跳过入库`)
      progressItem.status = 'SUCCESS'
      progressItem.progress = 100
      return
    }

    // 开始轮询任务状态
    startPolling(res.task_id)
  } catch (err) {
    const error = err as Error
    ElMessage.error(error.message || `「${file.name}」上传失败`)
  } finally {
    isUploading.value = false
  }
}

/** 轮询任务状态 */
function startPolling(taskId: string): void {
  const poll = async () => {
    try {
      const task = await knowledgeService.getTaskStatus(taskId)
      const item = uploadProgressList.value.find((u) => u.taskId === taskId)
      if (!item) return

      item.status = task.status
      item.progress = task.progress

      if (task.error_message) {
        item.errorMessage = task.error_message
      }

      // 任务完成或失败，停止轮询
      if (task.status === 'SUCCESS' || task.status === 'FAILED' || task.status === 'CANCELLED') {
        stopPolling(taskId)
        if (task.status === 'SUCCESS') {
          emit('success')
        }
        return
      }
    } catch {
      // 轮询出错，继续尝试（最多由后端保留24小时）
    }

    // 继续轮询（2秒间隔）
    const timer = window.setTimeout(poll, 2000)
    pollTimers.value.set(taskId, timer)
  }

  // 首次延迟 1 秒开始
  const initialTimer = window.setTimeout(poll, 1000)
  pollTimers.value.set(taskId, initialTimer)
}

/** 停止轮询 */
function stopPolling(taskId: string): void {
  const timer = pollTimers.value.get(taskId)
  if (timer) {
    clearTimeout(timer)
    pollTimers.value.delete(taskId)
  }
}

/** 移除进度项 */
function removeProgressItem(taskId: string): void {
  stopPolling(taskId)
  uploadProgressList.value = uploadProgressList.value.filter((item) => item.taskId !== taskId)
}

/** 关闭弹窗 */
function handleClose(): void {
  // 清理所有轮询
  pollTimers.value.forEach((timer) => clearTimeout(timer))
  pollTimers.value.clear()
  uploadProgressList.value = []
  selectedCategory.value = 'GENERAL'
  selectedTags.value = []
  tagInput.value = ''
  dialogVisible.value = false
}

onUnmounted(() => {
  pollTimers.value.forEach((timer) => clearTimeout(timer))
  pollTimers.value.clear()
})
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="上传文档入库"
    width="640px"
    :close-on-click-modal="false"
    :before-close="handleClose"
  >
    <!-- 分类与标签设置 -->
    <el-form label-width="80px" class="upload-form">
      <el-form-item label="文档分类" required>
        <el-select v-model="selectedCategory" style="width: 200px">
          <el-option
            v-for="opt in categoryOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="标签">
        <div class="tag-input-wrapper">
          <el-tag
            v-for="tag in selectedTags"
            :key="tag"
            closable
            class="tag-item"
            @close="handleRemoveTag(tag)"
          >
            {{ tag }}
          </el-tag>
          <el-input
            v-model="tagInput"
            placeholder="输入标签，按回车添加"
            style="width: 180px"
            @keyup.enter="handleAddTag"
          />
        </div>
      </el-form-item>
    </el-form>

    <!-- 拖拽上传区域 -->
    <el-upload
      drag
      :auto-upload="false"
      :show-file-list="false"
      :accept="ACCEPT_TYPES"
      :multiple="true"
      @change="handleUploadChange"
    >
      <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
      <div class="el-upload__text">
        拖拽文件到此处，或 <em>点击上传</em>
      </div>
      <template #tip>
        <div class="el-upload__tip">
          支持 PDF、DOCX、XLSX、JPG、PNG 格式，单文件不超过 100MB
        </div>
      </template>
    </el-upload>

    <!-- 上传进度列表 -->
    <div v-if="uploadProgressList.length > 0" class="progress-list">
      <div class="progress-title">上传进度</div>
      <div
        v-for="item in uploadProgressList"
        :key="item.taskId"
        class="progress-item"
      >
        <div class="progress-header">
          <div class="file-info">
            <el-icon class="file-icon"><Document /></el-icon>
            <span class="file-name" :title="item.fileName">{{ item.fileName }}</span>
            <el-tag
              :type="TASK_STATUS_TYPES[item.status]"
              size="small"
              class="status-tag"
            >
              {{ TASK_STATUS_LABELS[item.status] }}
            </el-tag>
            <el-tag v-if="item.isDuplicate" type="warning" size="small">重复文件</el-tag>
          </div>
          <el-button
            v-if="item.status === 'SUCCESS' || item.status === 'FAILED' || item.status === 'CANCELLED'"
            link
            type="primary"
            size="small"
            @click="removeProgressItem(item.taskId)"
          >
            移除
          </el-button>
        </div>
        <el-progress
          :percentage="item.progress"
          :status="item.status === 'FAILED' ? 'exception' : item.status === 'SUCCESS' ? 'success' : undefined"
          :stroke-width="8"
        />
        <div v-if="item.errorMessage" class="error-message">
          {{ item.errorMessage }}
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.upload-form {
  margin-bottom: 16px;
}

.tag-input-wrapper {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.tag-item {
  margin-right: 0;
}

.progress-list {
  margin-top: 20px;
  max-height: 280px;
  overflow-y: auto;
}

.progress-title {
  font-size: 14px;
  font-weight: 500;
  color: #606266;
  margin-bottom: 12px;
}

.progress-item {
  padding: 12px;
  background-color: #f5f7fa;
  border-radius: 6px;
  margin-bottom: 10px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.file-icon {
  color: #409eff;
  flex-shrink: 0;
}

.file-name {
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

.status-tag {
  flex-shrink: 0;
}

.error-message {
  font-size: 12px;
  color: #f56c6c;
  margin-top: 6px;
}
</style>
