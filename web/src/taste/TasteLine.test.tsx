import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Taste } from '../api/types'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
import he from '../i18n/he.json'
import { renderApp } from '../test/renderApp'
import { TasteLine } from './TasteLine'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const norm = (s: string | null) => (s ?? '').replace(/\s+/g, ' ').trim()
const SPEC: Taste = { fit: 76, genres: ['Action', 'Adventure'], agreement: 74 }
const lineText = () => norm(screen.getByTestId('taste-line').textContent)

describe('TasteLine', () => {
  it('has the exact copy in Hebrew and English', () => {
    const pick = (s: typeof he) => [
      s.taste.match,
      s.taste.genres_one,
      s.taste.genres_two,
      s.taste.agree,
      s.taste.basedOnYou,
      s.taste.unlock,
      s.taste.unlockCta,
      s.wishlist.sort.recent,
      s.wishlist.sort.fit,
    ]
    expect(pick(he)).toEqual([
      '{{pct}}% התאמה',
      '{{a}} מתאים לך',
      '{{a}} ו{{b}} מתאימים לך',
      '{{pct}}% הסכמה עם {{name}}',
      'לפי הדירוגים שלך',
      'דרגו כמה כותרים כדי לקבל התאמת טעם',
      'לשאלון הטעם',
      'החדשים',
      'ההתאמה הגבוהה',
    ])
    expect(pick(en as unknown as typeof he)).toEqual([
      '{{pct}}% match',
      '{{a}} fits you',
      '{{a}} & {{b}} fit you',
      'you agree with {{name}} {{pct}}% of the time',
      'Based on your ratings',
      'Rate a few titles to unlock Taste Match',
      'Take the taste quiz',
      'Newest',
      'Best match',
    ])
  })

  it('shows the spec reason line and lower-cases the second English genre', async () => {
    await setLocale('en')
    renderApp(<TasteLine taste={{ fit: 76, genres: ['Action', 'Adventure'], agreement: 74 }} authorName="Gal" />)
    expect(lineText()).toBe(
      '76% match · Action & adventure fit you · you agree with Gal 74% of the time',
    )
  })

  it('Hebrew reason line', () => {
    renderApp(
      <TasteLine taste={{ fit: 76, genres: ['אקשן', 'הרפתקאות'], agreement: 74 }} authorName="Gal" />,
    )
    expect(lineText()).toBe('76% התאמה · אקשן והרפתקאות מתאימים לך · 74% הסכמה עם Gal')
  })

  it('names one genre', async () => {
    await setLocale('en')
    renderApp(<TasteLine taste={{ fit: 80, genres: ['Drama'], agreement: null }} authorName="Gal" />)
    expect(lineText()).toBe('80% match · Drama fits you')
  })

  it('falls back to Based on your ratings', () => {
    renderApp(<TasteLine taste={{ fit: 61, genres: [], agreement: null }} authorName="Gal" />)
    expect(lineText()).toBe('61% התאמה · לפי הדירוגים שלך')
  })

  it('ignores agreement without an author (title page)', async () => {
    await setLocale('en')
    renderApp(<TasteLine taste={{ fit: 79, genres: [], agreement: 70 }} />)
    expect(lineText()).toBe('79% match · Based on your ratings')
  })

  it('puts percentages and names in <bdi>', () => {
    renderApp(<TasteLine taste={SPEC} authorName="Gal" />)
    const bdis = Array.from(screen.getByTestId('taste-line').querySelectorAll('bdi')).map(
      (b) => b.textContent,
    )
    expect(bdis.sort()).toEqual(['74', '76', 'Gal'])
  })
})
