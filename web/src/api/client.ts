export type HealthResponse = {
  status: 'ok' | 'degraded'
  db: 'ok' | 'unreachable' | 'schema_missing'
}

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/** Resolves for both 200 (healthy) and 503 (degraded) answers; throws when the API can't be reached. */
export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/health`, { signal })
  return (await res.json()) as HealthResponse
}
