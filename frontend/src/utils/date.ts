export const formatDate = (val: string | undefined) => {
  if (!val) return ''
  const d = val.split('T')[0]
  const t = val.split('T')[1]?.split('.')[0]?.substring(0, 5)
  return t ? `${d} ${t}` : d
}

export const formatDateTime = () => {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
}

export const formatDateInput = (date: string) => date.replace(/-/g, '')
