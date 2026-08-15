/** Formatting helpers. Pure functions so they can be unit tested directly. */

export function formatPence(pence: number): string {
  const pounds = pence / 100
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency: 'GBP',
    minimumFractionDigits: pounds % 1 === 0 ? 0 : 2,
  }).format(pounds)
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function relativeTime(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((now.getTime() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  return formatDate(iso)
}

export type Remaining = {
  days: number
  hours: number
  minutes: number
  seconds: number
  expired: boolean
}

export function timeRemaining(target: string, now: Date = new Date()): Remaining {
  const ms = new Date(target).getTime() - now.getTime()
  if (ms <= 0) return { days: 0, hours: 0, minutes: 0, seconds: 0, expired: true }
  const seconds = Math.floor(ms / 1000)
  return {
    days: Math.floor(seconds / 86400),
    hours: Math.floor((seconds % 86400) / 3600),
    minutes: Math.floor((seconds % 3600) / 60),
    seconds: seconds % 60,
    expired: false,
  }
}

export function formatRemaining(remaining: Remaining): string {
  if (remaining.expired) return 'Locked'
  const { days, hours, minutes, seconds } = remaining
  if (days > 0) return `${days}d ${hours}h ${minutes}m`
  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`
  return `${minutes}m ${seconds}s`
}

/** Today in the browser's timezone, as the YYYY-MM-DD the API expects. */
export function isoToday(now: Date = new Date()): string {
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

/** The API sends decimals as strings like "56.0000"; show them as people write them. */
export function formatAmount(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '0'
  const numeric = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(numeric)) return String(value)
  return numeric.toLocaleString('en-GB', { maximumFractionDigits: 2 })
}

export function goalValueLabel(goal: {
  tracking_type: string
  current_value: string | null
  baseline_value: string | null
  target_value: string | null
  manual_progress_percentage: number | null
  completed_at: string | null
  unit: string | null
}): string {
  if (goal.tracking_type === 'MILESTONE') {
    return goal.completed_at ? 'Complete' : 'Not yet complete'
  }
  if (goal.tracking_type === 'MANUAL') {
    return `${goal.manual_progress_percentage ?? 0}% done`
  }
  const current = goal.current_value ?? goal.baseline_value
  const unit = goal.unit ? ` ${goal.unit}` : ''
  return `${formatAmount(current)} / ${formatAmount(goal.target_value)}${unit}`
}
