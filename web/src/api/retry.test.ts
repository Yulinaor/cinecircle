import { describe, expect, it } from 'vitest'
import { ApiError } from './client'
import { retryQuery } from './retry'

describe('retryQuery', () => {
  it.each([400, 401, 404, 409, 422, 429])('never retries a %i answer', (status) => {
    expect(retryQuery(0, new ApiError(status, 'x'))).toBe(false)
  })

  it('retries a 5xx answer twice', () => {
    const error = new ApiError(503, 'db_unavailable')
    expect([0, 1, 2, 3].map((n) => retryQuery(n, error))).toEqual([true, true, false, false])
  })

  it('retries a network failure (not an ApiError) twice', () => {
    const error = new TypeError('Failed to fetch')
    expect([0, 1, 2].map((n) => retryQuery(n, error))).toEqual([true, true, false])
  })
})
