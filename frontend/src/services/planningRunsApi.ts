import { apiGet } from './apiClient'

interface PlanningRunListItem {
  planning_run_id: number
}

interface PlanningRunListResponse {
  total: number
  items: PlanningRunListItem[]
}

// Backend has no "current" planning run concept - the frontend flow (per
// docs/ENDPOINTS.md) is to always take the most recently created run.
// Returns null if nothing has been uploaded/calculated yet.
export async function fetchLatestPlanningRunId(): Promise<number | null> {
  const list = await apiGet<PlanningRunListResponse>('/api/planning-runs?limit=1&offset=0')
  return list.items[0]?.planning_run_id ?? null
}
