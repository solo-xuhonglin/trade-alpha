<template>
  <!-- Stop Dialog -->
  <v-dialog v-model="stopDialog.show" max-width="400">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认停止任务
        <v-btn icon variant="text" size="small" @click="stopDialog.show = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <div class="mb-3">确定要停止{{ taskLabel }}任务「{{ stopDialog.task_id }}」吗？</div>
        <v-checkbox v-model="stopDialog.force" label="强制停止（终止进程）" color="error" hide-details />
      </v-card-text>
      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-btn variant="text" @click="stopDialog.show = false">取消</v-btn>
        <v-spacer />
        <v-btn color="warning" variant="text" :loading="stopDialog.loading" @click="confirmStop">确定停止</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Delete Dialog -->
  <v-dialog v-model="deleteDialog.show" max-width="400">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认删除
        <v-btn icon variant="text" size="small" @click="deleteDialog.show = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>此操作不可撤销，确定要删除{{ taskLabel }}任务「{{ deleteDialog.task_id }}」吗？</v-card-text>
      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-btn variant="text" @click="deleteDialog.show = false">取消</v-btn>
        <v-spacer />
        <v-btn color="error" variant="text" :loading="deleteDialog.loading" @click="confirmDelete">删除</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Active Tasks Table -->
  <v-card border rounded>
    <v-card-title>{{ title }}</v-card-title>
    <v-card-text>
      <v-data-table
        v-if="tasks.length > 0"
        :headers="tableHeaders"
        :items="tasks"
        hide-default-footer
      >
        <template v-slot:item.status="{ item }">
          <StatusChip :status="item.status" />
        </template>
        <template v-slot:item.progress="{ item }">
          <div class="d-flex flex-column">
            <div class="text-caption text-medium-emphasis" style="white-space: pre-line;">
              {{ item.progress_message || `${item.progress.toFixed(1)}%` }}
            </div>
            <v-progress-linear :value="item.progress" height="4" class="mt-1" />
          </div>
        </template>
        <template v-slot:item.created_at="{ item }">
          {{ formatDate(item.created_at) }}
        </template>
        <template v-if="showErrorColumn" v-slot:item.error_message="{ item }">
          <span class="text-error">{{ item.error_message }}</span>
        </template>
        <template v-slot:item.actions="{ item }">
          <v-btn
            v-if="item.status === 'failed' || item.status === 'cancelled' || item.status === 'completed'"
            color="error"
            variant="text"
            size="small"
            @click="deleteDialog.task_id = item.task_id; deleteDialog.show = true"
          >
            删除
          </v-btn>
          <v-btn
            v-else-if="item.status === 'running'"
            color="warning"
            variant="text"
            size="small"
            @click="stopDialog.task_id = item.task_id; stopDialog.force = false; stopDialog.show = true"
          >
            停止
          </v-btn>
        </template>
      </v-data-table>
      <div v-else class="text-center text-medium-emphasis pa-4">暂无运行中的任务</div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import StatusChip from './StatusChip.vue'
import { formatDate } from '@/utils/date'

const props = defineProps<{
  tasks: any[]
  taskLabel: string
  title: string
  showErrorColumn?: boolean
  apiStop?: (taskId: string, force: boolean) => Promise<any>
  apiDelete?: (taskId: string) => Promise<any>
}>()

const emit = defineEmits<{
  stopped: [taskId: string]
  deleted: [taskId: string]
}>()

const stopDialog = ref({ show: false, loading: false, task_id: '', force: false })
const deleteDialog = ref({ show: false, loading: false, task_id: '' })

const tableHeaders = computed(() => {
  const headers = [
    { title: '任务ID', key: 'task_id' },
    { title: '状态', key: 'status' },
    { title: '进度', key: 'progress' },
  ]
  if (props.showErrorColumn !== false) {
    headers.push({ title: '错误信息', key: 'error_message', minWidth: 200 })
  }
  headers.push(
    { title: '创建时间', key: 'created_at' },
    { title: '操作', key: 'actions', sortable: false },
  )
  return headers
})

const confirmStop = async () => {
  stopDialog.value.loading = true
  try {
    await props.apiStop?.(stopDialog.value.task_id, stopDialog.value.force)
    emit('stopped', stopDialog.value.task_id)
    stopDialog.value.show = false
  } catch {
    // error handled by parent
  } finally {
    stopDialog.value.loading = false
  }
}

const confirmDelete = async () => {
  deleteDialog.value.loading = true
  try {
    await props.apiDelete?.(deleteDialog.value.task_id)
    emit('deleted', deleteDialog.value.task_id)
    deleteDialog.value.show = false
  } catch {
    // error handled by parent
  } finally {
    deleteDialog.value.loading = false
  }
}
</script>