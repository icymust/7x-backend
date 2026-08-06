import { API_BASE_URL } from './apiClient'

export interface PlanningCalculationResult {
  planning_run_id: number
  dataset_id: number
  filename: string
  row_count: number
  model_version?: string
  horizon_start?: string | null
  horizon_end?: string | null
}

export async function calculateWorkbook(
  file: File,
): Promise<PlanningCalculationResult> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE_URL}/api/planning/calculate`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    let message = `Calculation failed with status ${response.status}`

    try {
      const payload = await response.json() as { detail?: unknown }
      if (typeof payload.detail === 'string') {
        message = payload.detail
      }
    } catch {
      // Keep the status-based message when the backend response is not JSON.
    }

    throw new Error(message)
  }

  return response.json() as Promise<PlanningCalculationResult>
}
