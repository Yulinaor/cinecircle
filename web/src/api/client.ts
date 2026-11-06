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

/** A non-2xx API answer. `detail` is the server's error code (e.g. `username_taken`), or "error". */
export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export type ApiInit = {
  token: string
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
}

/** Authenticated JSON request. 204 resolves `undefined`; any non-2xx throws {@link ApiError}. */
export async function apiFetch<T>(path: string, init: ApiInit): Promise<T> {
  const { token, method = 'GET', body, signal } = init
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  })
  if (!res.ok) {
    let detail = 'error'
    try {
      const data: unknown = await res.json()
      if (data && typeof data === 'object' && 'detail' in data && typeof data.detail === 'string') {
        detail = data.detail
      }
    } catch {
      // Not JSON (proxy error page, empty body): keep the generic code.
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
