import { apiGet } from './apiClient'
import { fetchLatestPlanningRunId } from './planningRunsApi'

export interface MonthlyDemandPoint {
  month: string
  source: 'actual' | 'ml_forecast'
  orders: number
  average_orders_per_day: number
  covered_days: number
  date_from: string
  date_to: string
}

export interface DemandAnalyticsResponse {
  planning_run_id: number
  dataset_id: number
  model_version: string
  historical_total_orders: number
  forecast_total_orders: number
  historical_monthly: MonthlyDemandPoint[]
  forecast_monthly: MonthlyDemandPoint[]
}

export async function fetchLatestDemandAnalytics(): Promise<DemandAnalyticsResponse | null> {
  const planningRunId = await fetchLatestPlanningRunId()

  if (planningRunId === null) {
    return null
  }

  return apiGet<DemandAnalyticsResponse>(
    `/api/planning-runs/${planningRunId}/demand-analytics`,
  )
}
