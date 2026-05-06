<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { projectService } from '@/api/project'
import type {
  ProjectCreateRequest,
  ProjectUpdateRequest,
  ProjectDetail,
  ProjectStatus,
} from '@/types/project'

interface Props {
  visible: boolean
  project?: ProjectDetail | null
}

const props = withDefaults(defineProps<Props>(), {
  project: null,
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  success: []
}>()

const formRef = ref<FormInstance | null>(null)
const loading = ref(false)

const isEdit = computed(() => !!props.project)
const dialogTitle = computed(() => (isEdit.value ? '编辑项目' : '创建项目'))

const form = reactive<ProjectCreateRequest & { status?: ProjectStatus }>({
  name: '',
  client: '',
  industry: '',
  region: '',
  tenderDate: '',
  budgetAmount: '',
  tenderAgency: '',
  description: '',
  deadline: '',
  status: undefined,
})

const rules: FormRules = {
  name: [
    { required: true, message: '请输入项目名称', trigger: 'blur' },
    { max: 512, message: '项目名称不超过512字符', trigger: 'blur' },
  ],
  client: [
    { required: true, message: '请输入客户名称', trigger: 'blur' },
    { max: 256, message: '客户名称不超过256字符', trigger: 'blur' },
  ],
  industry: [{ max: 64, message: '行业分类不超过64字符', trigger: 'blur' }],
  region: [{ max: 64, message: '地区不超过64字符', trigger: 'blur' }],
  tenderDate: [{ required: true, message: '请选择开标日期', trigger: 'change' }],
  deadline: [{ required: true, message: '请选择递交截止时间', trigger: 'change' }],
  budgetAmount: [{ pattern: /^\d+(\.\d{1,2})?$/, message: '金额格式不正确', trigger: 'blur' }],
  tenderAgency: [{ max: 256, message: '招标代理机构不超过256字符', trigger: 'blur' }],
}

/** 重置表单 */
function resetForm(): void {
  form.name = ''
  form.client = ''
  form.industry = ''
  form.region = ''
  form.tenderDate = ''
  form.budgetAmount = ''
  form.tenderAgency = ''
  form.description = ''
  form.deadline = ''
  form.status = undefined
  formRef.value?.resetFields()
}

/** 打开弹窗时回填数据 */
watch(
  () => props.visible,
  (val) => {
    if (val) {
      if (props.project) {
        form.name = props.project.name
        form.client = props.project.client
        form.industry = props.project.industry ?? ''
        form.region = props.project.region ?? ''
        form.tenderDate = props.project.tenderDate
        form.budgetAmount = props.project.budgetAmount ?? ''
        form.tenderAgency = props.project.tenderAgency ?? ''
        form.description = props.project.description ?? ''
        // deadline 为 ISO 字符串，日期选择器需要 Date 对象，在模板中处理
        form.deadline = (props.project as ProjectDetail & { deadline?: string }).deadline ?? ''
        form.status = props.project.status
      } else {
        resetForm()
      }
    }
  },
)

function handleClose(): void {
  emit('update:visible', false)
  resetForm()
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    if (isEdit.value && props.project) {
      const updateData: ProjectUpdateRequest = {
        name: form.name,
        client: form.client,
        industry: form.industry || undefined,
        region: form.region || undefined,
        tenderDate: form.tenderDate,
        budgetAmount: form.budgetAmount || undefined,
        status: form.status,
        tenderAgency: form.tenderAgency || undefined,
        description: form.description || undefined,
      }
      await projectService.updateProject(props.project.id, updateData)
      ElMessage.success('项目更新成功')
    } else {
      const createData: ProjectCreateRequest = {
        name: form.name,
        client: form.client,
        industry: form.industry || undefined,
        region: form.region || undefined,
        tenderDate: form.tenderDate,
        budgetAmount: form.budgetAmount || undefined,
        tenderAgency: form.tenderAgency || undefined,
        description: form.description || undefined,
        deadline: form.deadline,
      }
      await projectService.createProject(createData)
      ElMessage.success('项目创建成功')
    }
    emit('success')
    handleClose()
  } catch (err) {
    const error = err as Error & { code?: number }
    if (error.code === 40001) {
      ElMessage.error('项目名称已存在')
    } else {
      ElMessage.error(error.message || '操作失败')
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="dialogTitle"
    width="640px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" class="project-form">
      <el-form-item label="项目名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入项目名称" />
      </el-form-item>

      <el-form-item label="客户名称" prop="client">
        <el-input v-model="form.client" placeholder="请输入客户名称" />
      </el-form-item>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="行业分类" prop="industry">
            <el-input v-model="form.industry" placeholder="如：政务信息化" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="地区" prop="region">
            <el-input v-model="form.region" placeholder="如：北京市" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="开标日期" prop="tenderDate">
            <el-date-picker
              v-model="form.tenderDate"
              type="date"
              placeholder="选择开标日期"
              style="width: 100%"
              value-format="YYYY-MM-DD"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="截止时间" prop="deadline">
            <el-date-picker
              v-model="form.deadline"
              type="datetime"
              placeholder="选择递交截止时间"
              style="width: 100%"
              value-format="YYYY-MM-DDTHH:mm:ss"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="预算金额" prop="budgetAmount">
            <el-input v-model="form.budgetAmount" placeholder="单位：元">
              <template #append>元</template>
            </el-input>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="招标代理" prop="tenderAgency">
            <el-input v-model="form.tenderAgency" placeholder="招标代理机构" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item v-if="isEdit" label="项目状态" prop="status">
        <el-select v-model="form.status" placeholder="选择状态" style="width: 100%">
          <el-option label="草稿" value="DRAFT" />
          <el-option label="进行中" value="IN_PROGRESS" />
          <el-option label="审核中" value="REVIEWING" />
          <el-option label="已审批" value="APPROVED" />
          <el-option label="已递交" value="SUBMITTED" />
          <el-option label="已完成" value="COMPLETED" />
          <el-option label="已取消" value="CANCELLED" />
          <el-option label="已归档" value="ARCHIVED" />
        </el-select>
      </el-form-item>

      <el-form-item label="项目描述" prop="description">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          placeholder="请输入项目描述"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        {{ isEdit ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.project-form {
  padding-right: 20px;
}
</style>
