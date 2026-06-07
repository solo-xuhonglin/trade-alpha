<template>
  <v-chip :color="getStatusColor(status)" size="small">{{ getStatusText(status) }}</v-chip>
</template>

<script setup lang="ts">
import { getStatusColor, getStatusText } from '@/utils/taskStatus'

defineProps<{ status: string }>()
</script>