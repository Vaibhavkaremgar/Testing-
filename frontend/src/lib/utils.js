import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

export function formatDateInput(date) {
  if (!date) return ''
  const parsedDate = date instanceof Date ? date : new Date(date)
  if (Number.isNaN(parsedDate.getTime())) return ''
  return parsedDate.toISOString().slice(0, 10)
}

export function getRelativeDate(daysOffset = 0) {
  const date = new Date()
  date.setHours(0, 0, 0, 0)
  date.setDate(date.getDate() + daysOffset)
  return formatDateInput(date)
}

export function getDateRangePreset(preset = 'last_7_days') {
  const today = getRelativeDate(0)

  switch (preset) {
    case 'all_time':
      return { preset, from: '', to: '' }
    case 'today':
      return { preset, from: today, to: today }
    case 'yesterday': {
      const yesterday = getRelativeDate(-1)
      return { preset, from: yesterday, to: yesterday }
    }
    case 'last_30_days':
      return { preset, from: getRelativeDate(-29), to: today }
    case 'custom':
      return { preset, from: '', to: '' }
    case 'last_7_days':
    default:
      return { preset: 'last_7_days', from: getRelativeDate(-6), to: today }
  }
}

export function formatDateRangeLabel(range) {
  if (range?.preset === 'all_time') return 'All Time'
  if (!range?.from || !range?.to) return 'Select Date Range'

  const fromLabel = formatDate(range.from)
  const toLabel = formatDate(range.to)

  if (range.from === range.to) {
    return fromLabel
  }

  return `${fromLabel} - ${toLabel}`
}

export function formatDate(date) {
  return new Date(date).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}

export function formatDateTime(date) {
  return new Date(date).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

export function getScoreColor(score) {
  if (score === null || score === undefined) return 'text-muted-foreground'
  if (score <= 10) {
    if (score >= 8) return 'text-green-600 dark:text-green-400'
    if (score >= 6) return 'text-yellow-600 dark:text-yellow-400'
    return 'text-red-600 dark:text-red-400'
  }
  if (score >= 80) return 'text-green-600 dark:text-green-400'
  if (score >= 60) return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
}

export function getScoreBgColor(score) {
  if (score === null || score === undefined) return 'bg-muted'
  if (score <= 10) {
    if (score >= 8) return 'bg-green-100 dark:bg-green-900/30'
    if (score >= 6) return 'bg-yellow-100 dark:bg-yellow-900/30'
    return 'bg-red-100 dark:bg-red-900/30'
  }
  if (score >= 80) return 'bg-green-100 dark:bg-green-900/30'
  if (score >= 60) return 'bg-yellow-100 dark:bg-yellow-900/30'
  return 'bg-red-100 dark:bg-red-900/30'
}

export function getStageColor(stage) {
  const colors = {
    uploaded: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
    screening: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    shortlisted: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
    interview_scheduled: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
    interview_rescheduled: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
    no_show: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300',
    interviewed: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-300',
    selected: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
    rejected: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  }
  return colors[stage] || colors.uploaded
}

export function formatStage(stage) {
  return stage.split('_').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ')
}
