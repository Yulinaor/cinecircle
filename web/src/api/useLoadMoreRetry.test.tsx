import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useLoadMoreRetry } from './useLoadMoreRetry'

function setup(fetchNextPage: () => Promise<{ isError: boolean }>) {
  const refetch = vi.fn()
  const view = renderHook(
    ({ scope }) => useLoadMoreRetry({ hasNextPage: true, fetchNextPage, refetch }, scope),
    { initialProps: { scope: 'want' } },
  )
  return { refetch, ...view }
}

describe('useLoadMoreRetry', () => {
  it('retries the next page after a failed Load more, else refetches', async () => {
    const fetchNextPage = vi.fn().mockResolvedValue({ isError: true })
    const { result, refetch } = setup(fetchNextPage)

    act(() => result.current.retry())
    expect(refetch).toHaveBeenCalledTimes(1)

    await act(async () => result.current.loadMore())
    act(() => result.current.retry())
    expect(fetchNextPage).toHaveBeenCalledTimes(2)
    expect(refetch).toHaveBeenCalledTimes(1)

    // A Load more that works ends the retry-the-page mode.
    fetchNextPage.mockResolvedValue({ isError: false })
    await act(async () => result.current.retry())
    act(() => result.current.retry())
    expect(refetch).toHaveBeenCalledTimes(2)
  })

  it('forgets a failed Load more when the list changes', async () => {
    const fetchNextPage = vi.fn().mockResolvedValue({ isError: true })
    const { result, refetch, rerender } = setup(fetchNextPage)
    await act(async () => result.current.loadMore())

    rerender({ scope: 'watched' })
    act(() => result.current.retry())
    // Refetches the Watched list rather than loading the next Want page into it.
    expect(refetch).toHaveBeenCalledTimes(1)
    expect(fetchNextPage).toHaveBeenCalledTimes(1)
  })
})
