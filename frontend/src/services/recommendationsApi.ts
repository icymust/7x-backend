import { apiGet } from './apiClient'
import { fetchLatestPlanningRunId } from './planningRunsApi'

export type RecommendationReason =
  | 'capacity_is_sufficient'
  | 'emergency_outsourcing_required'
  | 'permanent_lead_time_missed'
  | 'planned_hiring'

export type RecommendationPriority = 'low' | 'medium' | 'high' | 'critical'

export interface BackendRecommendation {
  target_permanent: number
  target_outsourced: number
  add_permanent: number
  add_outsourced: number
  permanent_start_by: string
  outsourced_start_by: string
  priority: RecommendationPriority
  reason: RecommendationReason
}

export interface BackendRecommendationRow {
  store_id: string
  time_bucket: string
  required_couriers: number
  available_couriers: number
  shortage: number
  surplus: number
  recommendation: BackendRecommendation
}

interface PlanningRunRecommendationsResponse {
  recommendations: BackendRecommendationRow[]
}

// One row per day the store had a recommendation attached, oldest to newest
// (the backend's own plan order). Returns [] if nothing has been
// uploaded/calculated yet, matching the other services' no-data behavior.
export async function fetchStoreRecommendations(storeId: string): Promise<BackendRecommendationRow[]> {
  const planningRunId = await fetchLatestPlanningRunId()

  if (planningRunId === null) {
    return []
  }

  const response = await apiGet<PlanningRunRecommendationsResponse>(
    `/api/planning-runs/${planningRunId}/recommendations?store_id=${encodeURIComponent(storeId)}`,
  )
  return response.recommendations
}
