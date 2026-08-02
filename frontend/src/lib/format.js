/**
 * Small display-formatting helpers shared by the dashboard components.
 * Kept separate from api.js (data fetching) - this file only ever
 * transforms values that are already in hand, never talks to the network.
 */

export function formatMoney(amount, currency) {
  if (amount === null || amount === undefined) return '—'
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: currency || 'INR',
      maximumFractionDigits: 0,
    }).format(amount)
  } catch {
    // Intl throws on an unrecognized currency code - fall back to a plain
    // "1234 XYZ" rather than crashing the results view over a display nicety.
    return `${amount} ${currency || ''}`.trim()
  }
}

export function formatDateRange(start, end) {
  if (!start || !end) return ''
  const opts = { month: 'short', day: 'numeric', year: 'numeric' }
  const s = new Date(start).toLocaleDateString('en-IN', opts)
  const e = new Date(end).toLocaleDateString('en-IN', opts)
  return `${s} – ${e}`
}

export function formatDateShort(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-IN', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

export function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diffMs = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' })
}
