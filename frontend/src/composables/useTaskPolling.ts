import { ref, onMounted, onUnmounted } from 'vue'

interface TaskPollingOptions<T> {
  pollFn: () => Promise<{ data: { items: T[] } }>
  filterFn?: (task: T) => boolean
  pollInterval?: number
  autoStart?: boolean
}

export function useTaskPolling<T extends { status: string }>({
  pollFn,
  filterFn = (t) => t.status !== 'completed',
  pollInterval = 3000,
  autoStart = true,
}: TaskPollingOptions<T>) {
  const activeTasks = ref<T[]>([])
  let pollIntervalId: number | null = null

  const poll = async () => {
    try {
      const res = await pollFn()
      const items = res.data.items.filter(filterFn)
      activeTasks.value = items

      const hasActive = items.some(t => t.status === 'pending' || t.status === 'running')
      if (!hasActive && pollIntervalId) {
        stopPolling()
      }
    } catch (e) {
      console.error('Poll error:', e)
    }
  }

  const startPolling = () => {
    if (pollIntervalId) {
      clearInterval(pollIntervalId)
      pollIntervalId = null
    }
    poll()
    pollIntervalId = window.setInterval(poll, pollInterval)
  }

  const stopPolling = () => {
    if (pollIntervalId) {
      clearInterval(pollIntervalId)
      pollIntervalId = null
    }
  }

  if (autoStart) {
    onMounted(startPolling)
  }

  onUnmounted(stopPolling)

  return {
    activeTasks,
    startPolling,
    stopPolling,
    poll,
  }
}
