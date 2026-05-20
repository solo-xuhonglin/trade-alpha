<template>
  <v-card border rounded class="mb-4">
    <v-toolbar flat>
      <v-toolbar-title>
        <v-icon color="medium-emphasis" icon="mdi-chart-box" size="x-small" start />
        分析记录
      </v-toolbar-title>
    </v-toolbar>
    <v-data-table :headers="headers" :items="records" :loading="loading">
      <template v-slot:item.ts_codes="{ item }">
        <span v-if="item.ts_codes.length > 3">{{ item.ts_codes.length }} 只</span>
        <span v-else>{{ item.ts_codes.join(', ') }}</span>
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn size="small" variant="text" color="info" prepend-icon="mdi-information-outline" @click="openDetailDialog(item)">详情</v-btn>
          <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="confirmDelete(item)">删除</v-btn>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-card v-if="error" border rounded class="mb-4" color="error">
    <v-card-text class="text-white">{{ error }}</v-card-text>
  </v-card>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认删除
        <v-btn icon variant="text" size="small" @click="deleteDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>此操作不可撤销，确定要删除分析「{{ deletingItem?.name }}」吗？</v-card-text>
      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false" />
        <v-spacer />
        <v-btn text="删除" color="error" @click="deleteRecord" :loading="deleting" />
      </v-card-actions>
    </v-card>
  </v-dialog>

  <AnalysisDetailDialog
    v-model:dialog="detailDialog"
    :title="detailItem?.name || ''"
    :result="detailResult"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { dataAnalysisApi, type AnalysisRecord, type AnalysisResult } from '@/api/dataAnalysis'
import AnalysisDetailDialog from '@/components/AnalysisDetailDialog.vue'

const loading = ref(false)
const records = ref<AnalysisRecord[]>([])
const error = ref('')
const deleteDialog = ref(false)
const deleting = ref(false)
const deletingItem = ref<AnalysisRecord | null>(null)
const detailDialog = ref(false)
const detailItem = ref<AnalysisRecord | null>(null)
const detailResult = ref<AnalysisResult | null>(null)

const headers = [
  { title: '名称', key: 'name' },
  { title: '创建时间', key: 'created_at' },
  { title: '日期范围', key: 'date_range' },
  { title: '股票数量', key: 'stock_count' },
  { title: '指标数量', key: 'field_count' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

const loadRecords = async () => {
  loading.value = true
  try {
    const res = await dataAnalysisApi.listResults()
    records.value = res.data.map(r => ({
      ...r,
      date_range: `${r.start_date} ~ ${r.end_date}`,
      stock_count: r.ts_codes.length,
      field_count: r.feature_fields.length,
    }))
  } catch (e) {
    console.error('Load records error:', e)
    error.value = '加载失败'
  } finally {
    loading.value = false
  }
}

const confirmDelete = (item: AnalysisRecord) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteRecord = async () => {
  if (!deletingItem.value) return
  deleting.value = true
  try {
    await dataAnalysisApi.deleteResult(deletingItem.value.id)
    deleteDialog.value = false
    deletingItem.value = null
    await loadRecords()
  } catch (e) {
    console.error('Delete error:', e)
    error.value = '删除失败'
  } finally {
    deleting.value = false
  }
}

const openDetailDialog = async (item: AnalysisRecord) => {
  detailItem.value = item
  try {
    const res = await dataAnalysisApi.getTaskStatus(item.task_id)
    if (res.data.result) {
      detailResult.value = res.data.result
    }
    detailDialog.value = true
  } catch (e) {
    console.error('Load detail error:', e)
    error.value = '加载详情失败'
  }
}

onMounted(() => {
  loadRecords()
})
</script>
