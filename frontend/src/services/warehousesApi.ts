import { apiGet } from './apiClient'
import { fetchLatestPlanningRunId } from './planningRunsApi'

// Only the fields the warehouse-list mapping actually reads. The backend has
// no dedicated "warehouse" resource - this is one row of a Planning Run's
// `plan` (one store, one day/time-bucket), and the richer store_name/zone/
// date/required_courier_hours/available_courier_hours fields only appear for
// the "official" multi-sheet upload flow, not the legacy one.
export interface BackendPlanRow {
  store_id: string
  store_name?: string
  emirate?: string
  zone?: string
  date?: string
  time_bucket: string
  available_permanent: number
  available_outsourced: number
  required_couriers: number
  available_couriers: number
  shortage: number
  surplus: number
  required_courier_hours?: number
  available_courier_hours?: number
}

interface PlanningRunDetailResponse {
  planning_run_id: number
  plan: BackendPlanRow[]
}

// Backend has no dedicated "warehouses" endpoint - a store only exists as a
// byproduct of an uploaded Planning Run. Take the most recently created run
// and return its plan rows for the caller to collapse into one snapshot per
// store. Returns [] if nothing has been uploaded/calculated yet.
export async function fetchLatestPlanRows(): Promise<BackendPlanRow[]> {
  const planningRunId = await fetchLatestPlanningRunId()

  if (planningRunId === null) {
    return []
  }

  const detail = await apiGet<PlanningRunDetailResponse>(`/api/planning-runs/${planningRunId}`)
  return detail.plan
}

// A store shows up once per day/time-bucket in `plan` - collapse to
// whichever row is most recent per store_id, so the warehouse list reflects
// a "right now" snapshot rather than the full history.
export function latestRowPerStore(rows: BackendPlanRow[]): BackendPlanRow[] {
  const latestByStore = new Map<string, BackendPlanRow>()

  for (const row of rows) {
    const sortKey = row.date ?? row.time_bucket
    const existing = latestByStore.get(row.store_id)
    const existingKey = existing && (existing.date ?? existing.time_bucket)

    if (!existing || sortKey > existingKey!) {
      latestByStore.set(row.store_id, row)
    }
  }

  return [...latestByStore.values()]
}
