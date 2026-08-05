import { apiGet } from './apiClient'
import { fetchLatestPlanningRunId } from './planningRunsApi'

export type BackendNotificationType =
  | 'urgent_staff_shortage'
  | 'upcoming_shortage'
  | 'hiring_start_required'
  | 'staff_surplus'

// 'low' is theoretically possible from the recommendation engine's priority
// field but build_notifications filters those rows out before they reach
// this response - kept here defensively in case that changes.
export type BackendNotificationSeverity = 'critical' | 'high' | 'medium' | 'warning' | 'surplus' | 'low'

export interface BackendNotification {
  notification_id: string
  type: BackendNotificationType
  severity: BackendNotificationSeverity
  title: string
  store_id: string
  time_bucket: string
  date: string
  shortage: number
  surplus: number
  add_permanent: number
  add_outsourced: number
  reason: string | null
  action_by: string | null
}

interface PlanningRunNotificationsResponse {
  planning_run_id: number
  notifications: BackendNotification[]
}

// Backend recomputes notifications fresh from the latest Planning Run's
// plan on every request - one entry per (store, day, issue type), with no
// pagination, no date filtering applied here, and no persisted read/unread
// state. For a 900-row/~10-store/90-day plan this is ~1800 rows; the caller
// is expected to sort/cap for display.
export async function fetchLatestNotifications(): Promise<BackendNotification[]> {
  const planningRunId = await fetchLatestPlanningRunId()

  if (planningRunId === null) {
    return []
  }

  const response = await apiGet<PlanningRunNotificationsResponse>(
    `/api/planning-runs/${planningRunId}/notifications`,
  )
  return response.notifications
}
