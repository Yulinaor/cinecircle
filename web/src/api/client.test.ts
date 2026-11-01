import { describe, expect, it } from 'vitest'
import { DEFAULT_API_URL, resolveApiUrl } from './client'

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
