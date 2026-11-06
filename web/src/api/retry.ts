import { ApiError } from './client'

/** Retries a failed query up to twice, but never a 4xx answer: asking again cannot change it. */
export function retryQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status < 500) return false
  return failureCount < 2
}
