import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { MyStats } from '../api/types'
import { AppRoutes } from '../app/routes'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
import he from '../i18n/he.json'
import { EMPTY_STATS, fakeApi, MY_STATS } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { findPhysicalUtilities } from '../test/rtl'
import { StatsPage } from './StatsPage'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const HE = 'GET /me/stats?lang=he'
const EN = 'GET /me/stats?lang=en'

function setup(stats: unknown = MY_STATS, key = HE) {
  const fake = fakeApi({ [key]: stats })
  const view = renderApp(<StatsPage />, { api: fake.api, route: '/stats' })
  return { fake, ...view }
}

/** The innermost element whose whole text is `text` (a line with <bdi> numbers inside it). */
const line = (text: string) => {
  const hits = screen.getAllByText((_, el) => el?.textContent === text)
  return hits[hits.length - 1]!
}

const withGap = (mean_gap: number): MyStats => ({ ...MY_STATS, imdb: { ...MY_STATS.imdb, mean_gap } })

describe('StatsPage', () => {
  it('renders the four charts from /me/stats', async () => {
    setup()
    expect(screen.getByRole('heading', { level: 1, name: he.stats.title })).toBeInTheDocument()
    await screen.findByRole('region', { name: he.stats.distribution.title })
    expect(screen.getByText(he.stats.privateNote)).toBeInTheDocument()
    expect(line('דירגת 12 כותרים')).toBeInTheDocument()

    const dist = screen.getByRole('region', { name: he.stats.distribution.title })
    const columns = within(dist).getAllByRole('listitem')
    expect(columns).toHaveLength(10)
    expect(columns.map((c) => c.textContent)).toEqual(
      MY_STATS.distribution.map((b) => `${b.count}${b.rating}`),
    )

    const genres = screen.getByRole('region', { name: he.stats.genres.title })
    expect(within(genres).getByText('דרמה')).toBeInTheDocument()
    expect(line('3 כותרים · ממוצע 7.8')).toBeInTheDocument()

    const imdb = screen.getByRole('region', { name: he.stats.imdb.title })
    expect(within(imdb).getAllByRole('listitem')).toHaveLength(5)
    expect(within(imdb).getByText('בערך אותו דבר')).toBeInTheDocument()
    expect(line('על סמך 9 כותרים עם דירוג IMDb')).toBeInTheDocument()

    const agree = screen.getByRole('region', { name: he.stats.agreement.title })
    expect(within(agree).getByText('Gal')).toBeInTheDocument()
    expect(line('74% הסכמה · 5 כותרים משותפים')).toBeInTheDocument()
  })

  it('renders in English with singular and plural counts', async () => {
    await setLocale('en')
    setup({ ...MY_STATS, rated: 1 }, EN)
    await screen.findAllByRole('region')
    expect(line('1 title rated')).toBeInTheDocument()
    expect(line('3 titles · average 7.8')).toBeInTheDocument()
    expect(line('74% agreement · 5 titles in common')).toBeInTheDocument()
    expect(line('Based on 9 titles with an IMDb rating')).toBeInTheDocument()
  })

  it('says "one title" in Hebrew for a single rating', async () => {
    setup({ ...MY_STATS, rated: 1 })
    expect(await screen.findByText('דירגת כותר אחד')).toBeInTheDocument()
  })

  it('links each agreed account to its profile', async () => {
    setup()
    const link = await screen.findByRole('link', { name: 'Gal' })
    expect(link).toHaveAttribute('href', '/u/gal')
    expect(link.className).toContain('min-h-11')
    expect(screen.getByRole('link', { name: 'Ron' })).toHaveAttribute('href', '/u/ron')
  })

  it('words the IMDb gap', async () => {
    const higher = setup(withGap(0.8))
    const higherLine = await screen.findByText(/בממוצע הדירוג שלך גבוה/)
    expect(higherLine).toHaveTextContent('בממוצע הדירוג שלך גבוה ב־0.8 מ־IMDb')
    expect(within(higherLine).getByText('0.8').tagName).toBe('BDI')
    higher.unmount()

    const lower = setup(withGap(-1.2))
    const lowerLine = await screen.findByText(/בממוצע הדירוג שלך נמוך/)
    expect(lowerLine).toHaveTextContent('בממוצע הדירוג שלך נמוך ב־1.2 מ־IMDb')
    expect(within(lowerLine).getByText('1.2').tagName).toBe('BDI')
    lower.unmount()

    setup(withGap(0.02))
    expect(await screen.findByText(he.stats.imdb.same)).toBeInTheDocument()
    expect(screen.queryByText(/בממוצע הדירוג שלך גבוה/)).toBeNull()
  })

  it('shows empty states for a new user', async () => {
    const { container } = setup(EMPTY_STATS)
    expect(await screen.findByText(he.stats.empty)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: he.stats.cta })).toHaveAttribute('href', '/post')
    expect(screen.queryByRole('region')).toBeNull()
    expect(screen.queryByTestId('bar')).toBeNull()
    expect(container.innerHTML).not.toMatch(/NaN|Infinity/)
  })

  it('says so inside a chart that has no data', async () => {
    setup({ ...MY_STATS, genres: [], agreement: [], imdb: { ...EMPTY_STATS.imdb } })
    const imdb = await screen.findByRole('region', { name: he.stats.imdb.title })
    expect(within(imdb).getByText(he.stats.imdb.empty)).toBeInTheDocument()
    expect(within(imdb).queryByRole('list')).toBeNull()
    const agree = screen.getByRole('region', { name: he.stats.agreement.title })
    expect(within(agree).getByText(he.stats.agreement.empty)).toBeInTheDocument()
    // No copy for "no genres": the section is left out rather than drawn empty.
    expect(screen.queryByRole('region', { name: he.stats.genres.title })).toBeNull()
    expect(screen.getByRole('region', { name: he.stats.distribution.title })).toBeInTheDocument()
  })

  it('isolates numbers in Hebrew', async () => {
    setup()
    await screen.findAllByRole('region')
    const isolates = within(line('74% הסכמה · 5 כותרים משותפים')).getAllByText(/^\d+%?$/)
    expect(isolates.map((el) => [el.tagName, el.getAttribute('dir'), el.textContent])).toEqual([
      ['BDI', 'ltr', '74%'],
      ['BDI', 'ltr', '5'],
    ])
    expect(document.documentElement.dir).toBe('rtl')
  })

  it('shows an error with retry, then the charts', async () => {
    let fail = true
    const { fake } = setup(() => {
      if (fail) throw new ApiError(500, 'boom')
      return MY_STATS
    })
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    fail = false
    await userEvent.setup({ delay: null }).click(screen.getByRole('button', { name: he.common.retry }))
    expect(await screen.findByRole('region', { name: he.stats.genres.title })).toBeInTheDocument()
    expect(fake.count(HE)).toBe(2)
  })

  it('is routed at /stats', async () => {
    const fake = fakeApi({ [HE]: MY_STATS })
    renderApp(<AppRoutes />, { api: fake.api, route: '/stats' })
    expect(await screen.findByRole('heading', { level: 1, name: he.stats.title })).toBeInTheDocument()
  })

  it('has copy for every bucket and uses no physical left/right utilities', () => {
    for (const key of ['much_lower', 'lower', 'same', 'higher', 'much_higher'] as const) {
      expect(he.stats.imdb.bucket[key]).toBeTruthy()
      expect(en.stats.imdb.bucket[key]).toBeTruthy()
    }
    const sources = import.meta.glob<string>(['./*.tsx', '!./*.test.tsx'], {
      query: '?raw',
      import: 'default',
      eager: true,
    })
    expect(Object.keys(sources).length).toBe(2)
    expect(Object.values(sources).flatMap((s) => findPhysicalUtilities(s))).toEqual([])
  })
})
