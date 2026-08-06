import { apiGet } from './apiClient'
import { fetchLatestPlanningRunId } from './planningRunsApi'

// Backend-computed per-day severity, worst-first: critical shortage beats
// high, which beats a plain shortage warning, which beats a surplus-only
// day - see _calculate_severity in daily_summary.py. Distinct from (and
// more meaningful than) DriverStatus, which only looks at one snapshot.
export type CalendarSeverity = 'critical' | 'high' | 'warning' | 'surplus' | 'normal'

export interface CalendarDay {
  date: string
  is_weekend: boolean
  is_public_holiday: boolean
  holiday_name: string | null
  severity: CalendarSeverity
  coverage_percent: number
  required_courier_slots: number
  available_courier_slots: number
  shortage_courier_slots: number
  surplus_courier_slots: number
  affected_stores: number
  recommendations_count: number
  planning_grain?: string
  forecast_orders?: number
  baseline_forecast_orders?: number
  predicted_orders?: number
  required_courier_hours?: number
  available_courier_hours?: number
}

interface PlanningRunCalendarResponse {
  calendar: CalendarDay[]
}

// One row per day the store has plan data for, aggregated across its whole
// day. With store_id set, the backend rebuilds this fresh from that store's
// plan rows rather than reading the Planning Run's own (network-wide)
// cached calendar - see get_planning_run_calendar in planning_runs.py.
// Returns [] if nothing's been uploaded/calculated yet, or if the
// date range falls outside the Planning Run's horizon.
export async function fetchStoreCalendar(
  storeId: string,
  dateFrom: string,
  dateTo: string,
): Promise<CalendarDay[]> {
  const planningRunId = await fetchLatestPlanningRunId()

  if (planningRunId === null) {
    return []
  }

  const params = new URLSearchParams({ store_id: storeId, date_from: dateFrom, date_to: dateTo })
  const response = await apiGet<PlanningRunCalendarResponse>(
    `/api/planning-runs/${planningRunId}/calendar?${params.toString()}`,
  )
  return response.calendar
}
