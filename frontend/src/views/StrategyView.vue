<template>
  <v-card border rounded>
    <v-data-table
      :headers="headers"
      :items="strategies"
      :loading="loading"
    >
      <template v-slot:top>
        <v-toolbar flat>
          <v-toolbar-title>
            <v-icon color="medium-emphasis" icon="mdi-strategy" size="x-small" start></v-icon>
            策略管理
          </v-toolbar-title>
          <v-btn
            prepend-icon="mdi-plus"
            rounded="lg"
            text="新建策略"
            border
            @click="openDialog()"
          ></v-btn>
        </v-toolbar>
      </template>

      <template v-slot:item.config="{ item }">
        <code>{{ JSON.stringify(item.config) }}</code>
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-2 justify-end">
          <v-icon color="medium-emphasis" icon="mdi-pencil" size="small" @click="openDialog(item)"></v-icon>
          <v-icon color="error" icon="mdi-delete" size="small" @click="confirmDelete(item)"></v-icon>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="dialog" max-width="500px">
    <v-card
      :subtitle="editingId ? '修改策略参数' : '创建新的交易策略'"
      :title="editingId ? '编辑策略' : '新建策略'"
    >
      <template v-slot:text>
        <v-row>
          <v-col cols="12">
            <v-text-field v-model="form.name" label="策略名称"></v-text-field>
          </v-col>
          <v-col cols="12">
            <v-select v-model="form.type" :items="strategyTypes" label="策略类型"></v-select>
          </v-col>
          <v-col cols="12">
            <v-textarea
              v-model="form.configJson"
              label="配置参数 (JSON)"
              hint='例如: {"max_positions": 10, "stop_loss_pct": 0.05}'
              persistent-hint
              rows="6"
            ></v-textarea>
          </v-col>
        </v-row>
      </template>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="dialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="保存" @click="saveStrategy"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card
      subtitle="此操作不可撤销"
      title="确认删除"
    >
      <template v-slot:text>
        确定要删除策略「{{ deletingItem?.name }}」吗？
      </template>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="删除" color="error" @click="deleteStrategy"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { strategyApi, type Strategy } from '@/api/strategy'

const loading = ref(false)
const dialog = ref(false)
const deleteDialog = ref(false)
const strategies = ref<Strategy[]>([])
const editingId = ref<string | null>(null)
const deletingItem = ref<Strategy | null>(null)
const strategyTypes = ['single', 'portfolio']

const form = ref({
  name: '',
  type: 'single',
  configJson: '{}',
  config: {} as Record<string, any>,
})

const headers = [
  { title: '名称', key: 'name' },
  { title: '类型', key: 'type' },
  { title: '配置', key: 'config' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' },
]

const loadStrategies = async () => {
  loading.value = true
  try {
    const res = await strategyApi.list()
    strategies.value = res.data
  } finally {
    loading.value = false
  }
}

const openDialog = (item?: Strategy) => {
  if (item) {
    editingId.value = item.id
    form.value = {
      name: item.name,
      type: item.type,
      configJson: JSON.stringify(item.config, null, 2),
      config: { ...item.config },
    }
  } else {
    editingId.value = null
    form.value = {
      name: 'default_strategy',
      type: 'single',
      configJson: '{}',
      config: {},
    }
  }
  dialog.value = true
}

const saveStrategy = async () => {
  try {
    form.value.config = JSON.parse(form.value.configJson)
  } catch {
    return
  }
  if (editingId.value) {
    await strategyApi.update(editingId.value, { name: form.value.name, config: form.value.config })
  } else {
    await strategyApi.create({ name: form.value.name, type: form.value.type, config: form.value.config })
  }
  dialog.value = false
  await loadStrategies()
}

const confirmDelete = (item: Strategy) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteStrategy = async () => {
  if (!deletingItem.value) return
  await strategyApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadStrategies()
}

onMounted(() => {
  loadStrategies()
})
</script>
