import { apiGet } from './apiClient'
import { fetchLatestPlanningRunId } from './planningRunsApi'

export type DecisionActionType =
  | 'schedule_reallocation'
  | 'store_transfer'
  | 'overtime'
  | 'planned_outsourcing'
  | 'permanent_hiring'
  | 'emergency_outsourcing'

export type DecisionPriority = 'low' | 'medium' | 'high' | 'critical'

export interface DecisionAction {
  action_id: string
  store_id: string
  from_store_id?: string
  shortage_period: { date_from: string; date_to: string }
  shortage_type: string
  time_horizon: string
  action_type: DecisionActionType
  couriers: number
  deadline: string
  priority: DecisionPriority
  reason: string
}

interface DecisionPlanResponse {
  planning_run_id: number
  actions: DecisionAction[]
}

// The Decision Engine's own rolling plan - what to do, computed rule-based
// from the Planning Run, with no natural-language description attached.
// Pair with assistantApi.explainDecisionAction() for that. Returns [] if
// nothing has been uploaded/calculated yet.
export async function fetchDecisionPlanActions(
  storeId: string,
): Promise<{ planningRunId: number; actions: DecisionAction[] }> {
  const planningRunId = await fetchLatestPlanningRunId()

  if (planningRunId === null) {
    return { planningRunId: 0, actions: [] }
  }

  const response = await apiGet<DecisionPlanResponse>(
    `/api/planning-runs/${planningRunId}/decision-plan?store_id=${encodeURIComponent(storeId)}`,
  )
  return { planningRunId, actions: response.actions }
}
