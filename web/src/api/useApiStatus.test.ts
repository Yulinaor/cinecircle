import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { HealthResponse } from './client'
import {
  OFFLINE_AFTER_MS,
  RECHECK_EVERY_MS,
  RETRY_EVERY_MS,
  useApiStatus,
  WAKING_AFTER_MS,
} from './useApiStatus'

const OK: HealthResponse = { status: 'ok', db: 'ok' }

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe('useApiStatus', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('is checking, then connected when health answers', async () => {
    const fetchHealth = vi.fn().mockResolvedValue(OK)
    const { result } = renderHook(() => useApiStatus(fetchHealth))
    expect(result.current).toBe('checking')
    await advance(0)
    expect(result.current).toBe('connected')
  })

  it('treats a degraded DB as connected', async () => {
    const fetchHealth = vi.fn().mockResolvedValue({ status: 'degraded', db: 'unreachable' })
    const { result } = renderHook(() => useApiStatus(fetchHealth))
    await advance(0)
    expect(result.current).toBe('connected')
  })

  it('shows waking after 3s without an answer, then connected', async () => {
    let resolve: (v: HealthResponse) => void = () => {}
    const fetchHealth = vi.fn(() => new Promise<HealthResponse>((r) => (resolve = r)))
    const { result } = renderHook(() => useApiStatus(fetchHealth))
    await advance(WAKING_AFTER_MS - 1)
    expect(result.current).toBe('checking')
    await advance(1)
    expect(result.current).toBe('waking')
    await act(async () => resolve(OK))
    expect(result.current).toBe('connected')
  })

  it('goes offline when the request throws, then recovers on retry', async () => {
    const fetchHealth = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(OK)
    const { result } = renderHook(() => useApiStatus(fetchHealth))
    await advance(0)
    expect(result.current).toBe('offline')
    await advance(RETRY_EVERY_MS)
    expect(result.current).toBe('connected')
    expect(fetchHealth).toHaveBeenCalledTimes(2)
  })

  it('keeps waking through a slow cold start and only goes offline after 90s', async () => {
    const fetchHealth = vi.fn(() => new Promise<HealthResponse>(() => {}))
    const { result } = renderHook(() => useApiStatus(fetchHealth))
    await advance(60000)
    expect(result.current).toBe('waking')
    await advance(29999)
    expect(result.current).toBe('waking')
    await advance(1)
    expect(result.current).toBe('offline')
    expect(OFFLINE_AFTER_MS).toBe(90000)
  })

  it('goes offline after the give-up time with no answer and aborts the request', async () => {
    const signals: AbortSignal[] = []
    const fetchHealth = vi.fn((signal?: AbortSignal) => {
      if (signal) signals.push(signal)
      return new Promise<HealthResponse>(() => {})
    })
    const { result } = renderHook(() => useApiStatus(fetchHealth))
    await advance(OFFLINE_AFTER_MS)
    expect(result.current).toBe('offline')
    expect(signals[0]?.aborted).toBe(true)
  })

  it('re-checks while connected and goes offline when the API dies', async () => {
    const fetchHealth = vi
      .fn()
      .mockResolvedValueOnce(OK)
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
    const { result } = renderHook(() => useApiStatus(fetchHealth))
    await advance(0)
    expect(result.current).toBe('connected')
    await advance(RECHECK_EVERY_MS)
    expect(result.current).toBe('offline')
    expect(fetchHealth).toHaveBeenCalledTimes(2)
  })

  it('stays connected when a re-check succeeds', async () => {
    const fetchHealth = vi.fn().mockResolvedValue(OK)
    const { result } = renderHook(() => useApiStatus(fetchHealth))
    await advance(0)
    await advance(RECHECK_EVERY_MS)
    expect(result.current).toBe('connected')
    expect(fetchHealth).toHaveBeenCalledTimes(2)
  })

  it('stops its timers when unmounted', async () => {
    const fetchHealth = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    const { unmount } = renderHook(() => useApiStatus(fetchHealth))
    await advance(0)
    unmount()
    await advance(RETRY_EVERY_MS * 3)
    expect(fetchHealth).toHaveBeenCalledTimes(1)
  })
})
