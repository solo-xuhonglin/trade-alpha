<template>
  <template v-if="type === 'boolean'">
    <v-chip :color="value ? 'success' : 'grey'" size="x-small">
      {{ value ? '是' : '否' }}
    </v-chip>
  </template>
  <template v-else-if="type === 'array' && Array.isArray(value)">
    <div class="d-flex flex-wrap ga-1">
      <v-chip v-for="v in value" :key="v" size="x-small" variant="outlined">{{ v }}</v-chip>
    </div>
  </template>
  <template v-else-if="value !== undefined && value !== null">
    {{ String(value) }}
  </template>
  <template v-else>
    -
  </template>
</template>

<script setup lang="ts">
defineProps<{
  value: any
  type?: string
}>()
</script>