<template>
  <v-card border rounded>
    <v-card v-if="errorMsg" border rounded class="mb-4" color="error">
      <v-card-text class="text-white">{{ errorMsg }}</v-card-text>
    </v-card>

    <v-data-table-server
      :headers="headers"
      :items="logs"
      :items-length="total"
      :loading="loading"
      :items-per-page="pageSize"
      v-model:page="page"
      @update:options="fetchLogs"
      hover
      item-value="id"
    >
      <template v-slot:top>
        <v-toolbar flat>
          <v-toolbar-title>
            <v-icon color="medium-emphasis" icon="mdi-history" size="x-small" start />
            执行历史
          </v-toolbar-title>
          <v-spacer />
          <v-select
            v-model="filterTaskKey"
            :items="taskKeyOptions"
            label="任务类型"
            clearable
            hide-details
            style="max-width: 200px"
            class="mr-2"
            @update:model-value="page = 1; fetchLogs()"
          />
          <v-btn prepend-icon="mdi-refresh" rounded="lg" text="刷新" border @click="fetchLogs" :loading="loading" />
        </v-toolbar>
      </template>

      <template v-slot:item.started_at="{ item }">
        {{ formatTime(item.started_at) }}
      </template>

      <template v-slot:item.duration_ms="{ item }">
        {{ item.duration_ms != null ? (item.duration_ms / 1000).toFixed(1) + 's' : '-' }}
      </template>

      <template v-slot:item.status="{ item }">
        <v-chip
          :color="item.status === 'completed' ? 'success' : item.status === 'failed' ? 'error' : 'warning'"
          size="x-small"
        >
          {{ item.status === 'completed' ? '成功' : item.status === 'failed' ? '失败' : '运行中' }}
        </v-chip>
      </template>

      <template v-slot:item.result="{ item }">
        {{ item.result_message || item.error_message || '-' }}
      </template>
    </v-data-table-server>
  </v-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { getLogs, type ScheduledTaskLogItem } from '@/api/scheduledTask'

const logs = ref<ScheduledTaskLogItem[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const filterTaskKey = ref<string | undefined>(undefined)
const errorMsg = ref<string | null>(null)

const taskKeyOptions = [
  { title: '数据同步', value: 'data_sync' },
  { title: '数据计数更新', value: 'data_count' },
  { title: '每日更新', value: 'daily_update' },
]

const headers = [
  { title: '任务', key: 'task_name', sortable: false },
  { title: '开始时间', key: 'started_at', sortable: false, width: 170 },
  { title: '耗时', key: 'duration_ms', sortable: false, width: 80 },
  { title: '状态', key: 'status', sortable: false, width: 80 },
  { title: '结果', key: 'result', sortable: false },
]

function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { hour12: false })
}

async function fetchLogs() {
  loading.value = true
  errorMsg.value = null
  try {
    const res = await getLogs({
      task_key: filterTaskKey.value,
      page: page.value,
      page_size: pageSize,
    })
    logs.value = res.data.items
    total.value = res.data.total
  } catch (e: any) {
    errorMsg.value = '加载失败: ' + (e.message || e)
  } finally {
    loading.value = false
  }
}
</script>