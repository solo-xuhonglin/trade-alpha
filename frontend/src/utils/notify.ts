// Global notification service for toast/snackbar
import { ref } from 'vue'

export interface Notification {
  id: number
  message: string
  type: 'success' | 'error' | 'info' | 'warning'
  duration?: number
}

const notifications = ref<Notification[]>([])
let nextId = 0

export const notifyService = {
  notifications,

  /**
   * Show a notification
   */
  show(
    message: string,
    type: 'success' | 'error' | 'info' | 'warning' = 'info',
    duration: number = 5000
  ): number {
    const id = nextId++
    notifications.value.push({ id, message, type, duration })
    return id
  },

  /**
   * Show success notification
   */
  success(message: string, duration?: number): number {
    return notifyService.show(message, 'success', duration)
  },

  /**
   * Show error notification
   */
  error(message: string, duration?: number): number {
    return notifyService.show(message, 'error', duration)
  },

  /**
   * Show info notification
   */
  info(message: string, duration?: number): number {
    return notifyService.show(message, 'info', duration)
  },

  /**
   * Show warning notification
   */
  warning(message: string, duration?: number): number {
    return notifyService.show(message, 'warning', duration)
  },

  /**
   * Remove a notification by id
   */
  remove(id: number): void {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.value.splice(index, 1)
    }
  },
}
