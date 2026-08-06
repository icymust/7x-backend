import { API_BASE_URL } from './apiClient'

export interface ServiceHealth {
  id: 'backend' | 'database' | 'ollama'
  name: string
  description: string
  available: boolean
  status: string
  details: string
}

interface HealthPayload {
  status?: string
  database?: string
  enabled?: boolean
  model?: string
  model_available?: boolean
  fallback_available?: boolean
  detail?: string
}

async function requestHealth(
  path: string,
): Promise<{ response: Response; payload: HealthPayload }> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  let payload: HealthPayload = {}

  try {
    payload = await response.json() as HealthPayload
  } catch {
    // The HTTP status is enough when the response is not JSON.
  }

  return { response, payload }
}

export async function fetchServiceHealth(): Promise<ServiceHealth[]> {
  const checks = [
    requestHealth('/health'),
    requestHealth('/health/database'),
    requestHealth('/health/ollama'),
  ]

  const results = await Promise.allSettled(checks)

  const backend = results[0].status === 'fulfilled'
    ? results[0].value
    : null
  const database = results[1].status === 'fulfilled'
    ? results[1].value
    : null
  const ollama = results[2].status === 'fulfilled'
    ? results[2].value
    : null

  const ollamaPayload = ollama?.payload
  const ollamaAvailable = Boolean(
    ollama?.response.ok
    && ollamaPayload?.status === 'ok'
    && ollamaPayload.model_available,
  )

  return [
    {
      id: 'backend',
      name: 'Backend API',
      description: 'FastAPI application',
      available: Boolean(backend?.response.ok && backend.payload.status === 'ok'),
      status: backend?.payload.status ?? 'unavailable',
      details: backend?.response.ok ? 'API is responding' : 'API is unavailable',
    },
    {
      id: 'database',
      name: 'PostgreSQL',
      description: 'Planning runs and datasets storage',
      available: Boolean(
        database?.response.ok
        && database.payload.status === 'ok'
        && database.payload.database === 'connected',
      ),
      status: database?.payload.status ?? 'unavailable',
      details: database?.response.ok
        ? 'Database connection is healthy'
        : database?.payload.detail ?? 'Database is unavailable',
    },
    {
      id: 'ollama',
      name: 'Ollama LLM',
      description: ollamaPayload?.model
        ? `Explanation model: ${ollamaPayload.model}`
        : 'AI explanation service',
      available: ollamaAvailable,
      status: ollamaPayload?.status ?? 'unavailable',
      details: ollamaAvailable
        ? 'Model is connected and ready'
        : ollamaPayload?.status === 'disabled'
          ? 'Ollama is disabled; structured fallback is active'
          : ollamaPayload?.status === 'model_missing'
            ? 'Ollama is connected, but the configured model is missing'
            : 'Ollama is unavailable; structured fallback is active',
    },
  ]
}
