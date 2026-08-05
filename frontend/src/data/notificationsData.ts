import { warehouses } from './warehouseData'
import { fetchLatestNotifications, type BackendNotification, type BackendNotificationSeverity } from '../services/notificationsApi'

export type NotificationStatus = 'success' | 'warning' | 'critical'

export const NOTIFICATION_STATUS_COLOR: Record<NotificationStatus, string> = {
  success: '#16a34a',
  warning: '#d97706',
  critical: '#dc2626',
}

export interface Notification {
  id: string
  title: string
  text: string
  status: NotificationStatus
  read: boolean
  timestamp: string
  // Name of the warehouse this notification is about, matching a name in
  // warehouseData.ts - lets the UI offer a "View Warehouse" deep link.
  // Omitted for notifications not tied to a specific branch (hiring, etc).
  warehouseName?: string
}

// Only "critical" is a genuine emergency in the backend's own model
// (outsourcing deadline already missed). "high"/"medium"/"warning" all mean
// "needs attention soon, not on fire yet", so they collapse to warning.
// "surplus" is the only non-urgent state, so it borrows the "success" color -
// it's neutral/informational, not literally good news.
const SEVERITY_STATUS: Record<BackendNotificationSeverity, NotificationStatus> = {
  critical: 'critical',
  high: 'warning',
  medium: 'warning',
  warning: 'warning',
  surplus: 'success',
  low: 'success',
}

const SEVERITY_RANK: Record<BackendNotificationSeverity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  warning: 3,
  surplus: 4,
  low: 5,
}

// The full list from a real forecast horizon can run into the thousands
// (one row per store per day per issue type - backend has no pagination or
// dedup here). Sort worst-first and cap what actually renders.
const MAX_RENDERED_NOTIFICATIONS = 60

function formatDate(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00`)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function warehouseNameForStore(storeId: string): string | undefined {
  return warehouses.features.find((f) => f.properties.storeId === storeId)?.properties.name
}

// Backend only gives structured numbers (shortage/surplus counts, add_*,
// reason code, deadline) - this turns those real numbers into a sentence
// instead of inventing new information.
function buildText(n: BackendNotification, warehouseName: string | undefined): string {
  const store = warehouseName ?? n.store_id
  const additions = [
    n.add_permanent > 0 ? `${n.add_permanent} permanent` : null,
    n.add_outsourced > 0 ? `${n.add_outsourced} outsourced` : null,
  ].filter((part): part is string => part !== null)

  switch (n.type) {
    case 'urgent_staff_shortage':
      return `${store} is short ${n.shortage} courier${n.shortage === 1 ? '' : 's'} on ${formatDate(n.date)}. Outsourcing lead time has already passed - emergency coverage is required.`
    case 'upcoming_shortage':
      return `${store} is projected to be short ${n.shortage} courier${n.shortage === 1 ? '' : 's'} on ${formatDate(n.date)}.`
    case 'hiring_start_required': {
      const by = n.action_by ? ` by ${formatDate(n.action_by)}` : ''
      return additions.length
        ? `${store} needs to start hiring ${additions.join(' and ')}${by} to cover a projected shortage on ${formatDate(n.date)}.`
        : `${store} needs to start hiring${by} to cover a projected shortage on ${formatDate(n.date)}.`
    }
    case 'staff_surplus':
      return `${store} has a surplus of ${n.surplus} courier${n.surplus === 1 ? '' : 's'} on ${formatDate(n.date)}.`
    default:
      return `${store}: ${n.title} on ${formatDate(n.date)}.`
  }
}

function toNotification(n: BackendNotification): Notification {
  const warehouseName = warehouseNameForStore(n.store_id)

  return {
    id: n.notification_id,
    title: warehouseName ? `${n.title} — ${warehouseName}` : n.title,
    text: buildText(n, warehouseName),
    status: SEVERITY_STATUS[n.severity] ?? 'warning',
    // Backend recomputes these fresh on every request - there's no
    // persisted read/unread state anywhere, so everything starts unread.
    read: false,
    timestamp: formatDate(n.date),
    warehouseName,
  }
}

export const notifications: Notification[] = []

// True backend count before capping to MAX_RENDERED_NOTIFICATIONS, so the UI
// can say "showing 60 of 1800" instead of silently understating the total.
export let totalNotificationCount = 0

export async function loadNotifications(): Promise<void> {
  const backendNotifications = await fetchLatestNotifications()
  totalNotificationCount = backendNotifications.length

  const sorted = [...backendNotifications].sort((a, b) => {
    const rankDiff = SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]
    return rankDiff !== 0 ? rankDiff : a.date.localeCompare(b.date)
  })

  notifications.splice(0, notifications.length, ...sorted.slice(0, MAX_RENDERED_NOTIFICATIONS).map(toNotification))
}
