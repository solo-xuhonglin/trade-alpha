export const TASK_STATUS = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const

export const TASK_STATUS_LABELS: Record<string, string> = {
  [TASK_STATUS.PENDING]: '等待中',
  [TASK_STATUS.RUNNING]: '运行中',
  [TASK_STATUS.COMPLETED]: '已完成',
  [TASK_STATUS.FAILED]: '失败',
  [TASK_STATUS.CANCELLED]: '已取消',
}

export const TASK_STATUS_COLORS: Record<string, string> = {
  [TASK_STATUS.PENDING]: 'info',
  [TASK_STATUS.RUNNING]: 'warning',
  [TASK_STATUS.COMPLETED]: 'success',
  [TASK_STATUS.FAILED]: 'error',
  [TASK_STATUS.CANCELLED]: 'grey',
}

export const getStatusColor = (status: string) => TASK_STATUS_COLORS[status] || ''
export const getStatusText = (status: string) => TASK_STATUS_LABELS[status] || status
