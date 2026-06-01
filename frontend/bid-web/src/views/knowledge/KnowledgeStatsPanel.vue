<script setup lang="ts">
import { computed } from 'vue'
import type { KnowledgeStatsResponse, CategoryStat, ExpiringSoonItem } from '@/types'
import { DOC_CATEGORY_LABELS, DOC_CATEGORY_TYPES } from '@/types'

interface Props {
  stats: KnowledgeStatsResponse | null
  loading: boolean
}

const props = defineProps<Props>()

const healthScore = computed(() => props.stats?.health_score ?? 0)
const totalDocuments = computed(() => props.stats?.total_documents ?? 0)
const categoryStats = computed<CategoryStat[]>(() => props.stats?.category_stats ?? [])
const expiringSoon = computed<ExpiringSoonItem[]>(() => props.stats?.expiring_soon ?? [])

/** 健康度颜色 */
const healthColor = computed(() => {
  if (healthScore.value >= 80) return '#67c23a'
  if (healthScore.value >= 60) return '#e6a23c'
  return '#f56c6c'
})

/** 健康度状态文字 */
const healthStatusText = computed(() => {
  if (healthScore.value >= 80) return '健康'
  if (healthScore.value >= 60) return '一般'
  return '需关注'
})

/** 分类统计图表数据 */
const chartData = computed(() => {
  return categoryStats.value.map((item) => ({
    name: DOC_CATEGORY_LABELS[item.category as keyof typeof DOC_CATEGORY_LABELS] || item.category,
    value: item.count,
    type: DOC_CATEGORY_TYPES[item.category as keyof typeof DOC_CATEGORY_TYPES] || '',
  }))
})


</script>

<template>
  <div class="stats-panel">
    <el-row :gutter="16">
      <!-- 总文档数 -->
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="stat-card" v-loading="loading">
          <div class="stat-icon document-icon">
            <el-icon><Document /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ totalDocuments }}</div>
            <div class="stat-label">知识库文档总数</div>
          </div>
        </el-card>
      </el-col>

      <!-- 健康度 -->
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="stat-card" v-loading="loading">
          <div class="stat-icon health-icon">
            <el-icon><FirstAidKit /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value" :style="{ color: healthColor }">
              {{ healthScore.toFixed(0) }}
              <span class="stat-unit">分</span>
            </div>
            <div class="stat-label">
              健康度
              <el-tag :type="healthScore >= 80 ? 'success' : healthScore >= 60 ? 'warning' : 'danger'" size="small">
                {{ healthStatusText }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 分类统计 -->
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="stat-card category-card" v-loading="loading">
          <div class="stat-label category-title">分类分布</div>
          <div v-if="chartData.length === 0" class="empty-text">暂无数据</div>
          <div v-else class="category-list">
            <div v-for="item in chartData" :key="item.name" class="category-item">
              <el-tag :type="item.type as any" size="small">{{ item.name }}</el-tag>
              <span class="category-count">{{ item.value }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 过期预警 -->
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="stat-card expire-card" v-loading="loading">
          <div class="stat-icon expire-icon">
            <el-icon><Timer /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value" :class="{ 'text-danger': expiringSoon.length > 0 }">
              {{ expiringSoon.length }}
            </div>
            <div class="stat-label">30天内过期证书</div>
          </div>
          <div v-if="expiringSoon.length > 0" class="expire-list">
            <el-tooltip
              v-for="item in expiringSoon.slice(0, 3)"
              :key="item.doc_id"
              :content="`过期日期: ${item.expire_date}`"
              placement="top"
            >
              <el-tag type="danger" size="small" class="expire-tag">{{ item.title }}</el-tag>
            </el-tooltip>
            <el-tag v-if="expiringSoon.length > 3" type="info" size="small">
              +{{ expiringSoon.length - 3 }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.stats-panel {
  margin-bottom: 16px;
}

.stat-card {
  height: 140px;
  display: flex;
  align-items: center;
  position: relative;
  overflow: hidden;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 16px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  margin-right: 16px;
  flex-shrink: 0;
}

.document-icon {
  background-color: #ecf5ff;
  color: #409eff;
}

.health-icon {
  background-color: #f0f9eb;
  color: #67c23a;
}

.expire-icon {
  background-color: #fef0f0;
  color: #f56c6c;
}

.stat-content {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  line-height: 1.2;
}

.stat-unit {
  font-size: 14px;
  font-weight: 400;
  color: #909399;
  margin-left: 4px;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.text-danger {
  color: #f56c6c;
}

/* 分类卡片 */
.category-card :deep(.el-card__body) {
  flex-direction: column;
  align-items: flex-start;
}

.category-title {
  margin-top: 0;
  margin-bottom: 12px;
  font-weight: 500;
  color: #606266;
}

.category-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
}

.category-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.category-count {
  color: #606266;
  font-weight: 500;
}

.empty-text {
  font-size: 13px;
  color: #909399;
}

/* 过期预警卡片 */
.expire-card :deep(.el-card__body) {
  flex-wrap: wrap;
}

.expire-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  width: 100%;
}

.expire-tag {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
