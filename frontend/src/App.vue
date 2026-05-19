<template>
  <AppLayout />
  
  <!-- Global Notifications -->
  <v-snackbar
    v-for="notification in notifications"
    :key="notification.id"
    v-model="activeNotifications[notification.id]"
    :color="notification.type"
    :timeout="notification.duration || 5000"
    location="top"
    @update:model-value="removeNotification(notification.id)"
  >
    {{ notification.message }}
    <template v-slot:actions>
      <v-btn
        text="关闭"
        variant="text"
        color="white"
        @click="removeNotification(notification.id)"
      ></v-btn>
    </template>
  </v-snackbar>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import AppLayout from '@/components/AppLayout.vue'
import { notifyService, type Notification } from '@/utils/notify'

const notifications = notifyService.notifications
const activeNotifications = ref<Record<number, boolean>>({})

const removeNotification = (id: number) => {
  notifyService.remove(id)
}

// Watch notifications to show/hide snackbars
watch(
  notifications,
  (newNotifications) => {
    const newActive: Record<number, boolean> = {}
    newNotifications.forEach((n) => {
      newActive[n.id] = true
    })
    activeNotifications.value = newActive
  },
  { deep: true }
)
</script>
