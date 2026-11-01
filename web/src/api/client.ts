export type HealthResponse = {
  status: 'ok' | 'degraded'
  db: 'ok' | 'unreachable' | 'schema_missing'
}

export const DEFAULT_API_URL = 'http://localhost:8000'

/** Blank → default; trailing slashes removed so `${API_URL}/health` never becomes `//health`. */
export function resolveApiUrl(raw: string | undefined): string {
  const url = (raw ?? '').trim().replace(/\/+$/, '')
  return url || DEFAULT_API_URL
}

export const API_URL: string = resolveApiUrl(import.meta.env.VITE_API_URL)

/** Resolves for both 200 (healthy) and 503 (degraded) answers; throws when the API can't be reached. */
export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/health`, { signal })
  return (await res.json()) as HealthResponse
}
