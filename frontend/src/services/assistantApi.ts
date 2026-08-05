import { apiPost } from './apiClient'

export interface ExplainResponse {
  source: 'ollama' | 'structured_fallback'
  language: string
  message: string | null
  context: unknown
}

// Turns one Decision Engine action into the natural-language explanation -
// the Decision Plan itself never describes actions in prose (see
// decisionPlanApi.ts). `message` is null when Ollama is disabled/unavailable
// or times out - callers should fall back to a structured summary in that
// case rather than showing nothing.
export async function explainDecisionAction(
  planningRunId: number,
  decisionActionId: string,
  language: 'en' | 'ru' = 'en',
): Promise<ExplainResponse> {
  return apiPost<ExplainResponse>('/api/assistant/explain', {
    planning_run_id: planningRunId,
    decision_action_id: decisionActionId,
    language,
  })
}
