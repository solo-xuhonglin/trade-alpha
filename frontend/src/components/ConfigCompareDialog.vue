<template>
  <v-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" max-width="900px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center text-h6 pa-4">
        <div class="d-flex align-center ga-2">
          <v-icon color="primary">mdi-compare</v-icon>
          配置对比
          <v-chip v-if="!showAll && visibleFields.length < fields.length" size="x-small" variant="outlined" color="warning" class="ml-1">
            隐藏 {{ fields.length - visibleFields.length }} 个相同项
          </v-chip>
        </div>
        <div class="d-flex align-center ga-2">
          <v-btn variant="tonal" size="small" :color="showAll ? '' : 'primary'" @click="showAll = !showAll" density="compact">
            <v-icon start size="small">{{ showAll ? 'mdi-filter-variant' : 'mdi-eye-outline' }}</v-icon>
            {{ showAll ? '仅显示不同' : '显示全部' }}
          </v-btn>
          <v-btn icon variant="text" size="small" @click="$emit('update:modelValue', false)">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </div>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-0">
        <v-table density="compact">
          <thead>
            <tr>
              <th class="text-left" style="width: 180px; min-width: 180px;">参数名</th>
              <th class="text-left" style="white-space: normal;" :class="isAllSame ? '' : 'bg-red-lighten-5'">{{ titleA || '配置A' }}</th>
              <th class="text-left" style="white-space: normal;" :class="isAllSame ? '' : 'bg-red-lighten-5'">{{ titleB || '配置B' }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="(field, idx) in visibleFields" :key="field.key">
              <tr v-if="field.group && (idx === 0 || visibleFields[idx - 1].group !== field.group)" class="bg-grey-lighten-3">
                <td colspan="3" class="font-weight-medium text-body-2">{{ field.group }}</td>
              </tr>
              <tr :class="!isFieldSame(field) ? 'bg-red-lighten-5' : ''">
                <td class="text-body-2">{{ field.label }}</td>
                <td :class="!isFieldSame(field) ? 'font-weight-medium' : ''">
                  <FormatValue :value="getFieldValue(configA, field.key)" :type="field.type" />
                </td>
                <td :class="!isFieldSame(field) ? 'font-weight-medium' : ''">
                  <FormatValue :value="getFieldValue(configB, field.key)" :type="field.type" />
                </td>
              </tr>
            </template>
          </tbody>
        </v-table>
      </v-card-text>
      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-spacer />
        <v-btn variant="text" @click="$emit('update:modelValue', false)">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import FormatValue from './FormatValue.vue'

export interface CompareField {
  key: string
  label: string
  group?: string
  type?: 'number' | 'string' | 'boolean' | 'array'
}

const props = withDefaults(defineProps<{
  modelValue: boolean
  configA?: Record<string, any>
  configB?: Record<string, any>
  fields: CompareField[]
  titleA?: string
  titleB?: string
}>(), {
  configA: null,
  configB: null,
})

defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const getFieldValue = (config: Record<string, any>, key: string): any => {
  return config[key]
}

const isFieldSame = (field: CompareField): boolean => {
  const a = getFieldValue(props.configA, field.key)
  const b = getFieldValue(props.configB, field.key)
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((v, i) => v === b[i])
  }
  return a === b
}

const showAll = ref(true)

const visibleFields = computed(() => {
  if (showAll.value) return props.fields
  return props.fields.filter(f => !isFieldSame(f))
})

const isAllSame = computed(() => {
  return props.fields.every(f => isFieldSame(f))
})
</script>