import { afterEach, describe, expect, it, vi } from 'vitest'
import { API_URL, ApiError, apiFetch, DEFAULT_API_URL, resolveApiUrl } from './client'

describe('resolveApiUrl', () => {
  it('uses the default when unset', () => expect(resolveApiUrl(undefined)).toBe(DEFAULT_API_URL))
  it('uses the default when empty or blank', () => {
    expect(resolveApiUrl('')).toBe(DEFAULT_API_URL)
    expect(resolveApiUrl('   ')).toBe(DEFAULT_API_URL)
  })
  it('drops trailing slashes', () =>
    expect(resolveApiUrl('https://cinecircle-api.onrender.com//')).toBe(
      'https://cinecircle-api.onrender.com',
    ))
  it('keeps a clean URL as is', () =>
    expect(resolveApiUrl('http://localhost:8000')).toBe('http://localhost:8000'))
})

describe('apiFetch', () => {
  afterEach(() => vi.unstubAllGlobals())

  function stubFetch(response: Response) {
    const fn = vi.fn(async (..._args: unknown[]) => response)
    vi.stubGlobal('fetch', fn)
    return fn
  }

  it('sends the bearer token and JSON body', async () => {
    const fetchMock = stubFetch(Response.json({ ok: true }))
    const result = await apiFetch<{ ok: boolean }>('/me/profile', {
      token: 'tok',
      method: 'POST',
      body: { username: 'dana' },
    })
    expect(result).toEqual({ ok: true })
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_URL}/me/profile`)
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('POST')
    expect(init.body).toBe(JSON.stringify({ username: 'dana' }))
    const headers = new Headers(init.headers)
    expect(headers.get('Authorization')).toBe('Bearer tok')
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('defaults to GET without a body', async () => {
    const fetchMock = stubFetch(Response.json({}))
    await apiFetch('/me', { token: 'tok' })
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.method).toBe('GET')
    expect(init.body).toBeUndefined()
  })

  it('throws ApiError with the server detail', async () => {
    stubFetch(Response.json({ detail: 'username_taken' }, { status: 409 }))
    const err = await apiFetch('/me/profile', { token: 't', method: 'POST' }).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(409)
    expect((err as ApiError).detail).toBe('username_taken')
  })

  it('ApiError keeps the JSON body', async () => {
    stubFetch(Response.json({ detail: 'post_exists', post_id: 5 }, { status: 409 }))
    const err = await apiFetch('/posts', { token: 't', method: 'POST' }).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).detail).toBe('post_exists')
    expect((err as ApiError).body).toEqual({ detail: 'post_exists', post_id: 5 })
    stubFetch(new Response('<html>', { status: 502 }))
    await expect(apiFetch('/x', { token: 't' })).rejects.toMatchObject({ body: null })
  })

  it('uses "error" when detail is not a string or the body is not JSON', async () => {
    stubFetch(Response.json({ detail: [{ msg: 'bad' }] }, { status: 422 }))
    await expect(apiFetch('/x', { token: 't' })).rejects.toMatchObject({ status: 422, detail: 'error' })
    stubFetch(new Response('<html>', { status: 502 }))
    await expect(apiFetch('/x', { token: 't' })).rejects.toMatchObject({ status: 502, detail: 'error' })
  })

  it('returns undefined for 204', async () => {
    stubFetch(new Response(null, { status: 204 }))
    expect(await apiFetch('/follows/x', { token: 't', method: 'DELETE' })).toBeUndefined()
  })
})
