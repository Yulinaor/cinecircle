import { describe, expect, it } from 'vitest'
import en from './en.json'
import he from './he.json'
import { applyDocumentLocale, DEFAULT_LOCALE, resolveInitialLocale } from './index'

const keys = (o: object, p = ''): string[] =>
  Object.entries(o)
    .flatMap(([k, v]) => (typeof v === 'object' && v !== null ? keys(v, `${p}${k}.`) : [`${p}${k}`]))
    .sort()

describe('locale', () => {
  it('he and en have identical keys', () => expect(keys(he)).toEqual(keys(en)))
  it('defaults to Hebrew with no storage', () => expect(resolveInitialLocale(null)).toBe('he'))
  it('uses a stored supported locale', () =>
    expect(resolveInitialLocale({ getItem: () => 'en' })).toBe('en'))
  it('ignores an unsupported stored value', () =>
    expect(resolveInitialLocale({ getItem: () => 'fr' })).toBe(DEFAULT_LOCALE))
  it('survives storage that throws', () =>
    expect(
      resolveInitialLocale({
        getItem: () => {
          throw new Error('SecurityError')
        },
      }),
    ).toBe('he'))
  it('sets dir and lang on <html>', () => {
    applyDocumentLocale('en')
    expect(document.documentElement.dir).toBe('ltr')
    expect(document.documentElement.lang).toBe('en')
    applyDocumentLocale('he')
    expect(document.documentElement.dir).toBe('rtl')
    expect(document.documentElement.lang).toBe('he')
  })
})
