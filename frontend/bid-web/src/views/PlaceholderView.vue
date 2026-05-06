<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const pageTitle = computed(() => (route.meta.title as string) || '页面')
</script>

<template>
  <div class="placeholder-page">
    <el-empty :description="`「${pageTitle}」功能开发中，敬请期待`" />
  </div>
</template>

<style scoped>
.placeholder-page {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}
</style>
