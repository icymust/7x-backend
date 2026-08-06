import { apiPost } from './apiClient'

// The natural-language explanation for one Decision Engine action, as a
// structured object rather than free-form prose - see SELECTED_ACTION_PROMPT
// in the backend's llm_service.py, which prompts Ollama for exactly this
// shape (and the backend validates it before returning, so if this type is
// present it's already well-formed). The courier count itself is shown
// straight from the Decision Engine's own action.couriers field instead of
// asking Ollama to restate it (see WarehouseAiSuggestions.vue).
export interface SelectedActionExplanation {
  recommendation: string
  timing: string
  reasons: string[]
}

export interface ExplainResponse {
  source: 'ollama' | 'structured_fallback'
  language: string
  message: SelectedActionExplanation | null
  context: unknown
}

// Turns one Decision Engine action into the natural-language explanation -
// the Decision Plan itself never describes actions in prose (see
// decisionPlanApi.ts). `message` is null when Ollama is disabled/unavailable,
// times out, or returns something that doesn't match the expected shape -
// callers should fall back to a structured summary in that case rather than
// showing nothing.
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
