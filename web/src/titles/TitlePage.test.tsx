import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { TitlePage as TitlePageData } from '../api/types'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
import he from '../i18n/he.json'
import { EXTERNAL_REVIEW, fakeApi, POST_CARD, WISHLIST_ITEM } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { ExternalRatings } from './ExternalRatings'
import { TitlePage } from './TitlePage'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const TITLE: TitlePageData = {
  id: 3,
  tmdb_id: 603,
  media_type: 'movie',
  imdb_id: 'tt0133093',
  name: 'האודיסאה',
  name_lang: 'he',
  overview: 'מסע ארוך הביתה.',
  overview_lang: 'he',
  year_start: 2026,
  year_end: null,
  runtime_min: 150,
  season_count: null,
  poster_url: 'https://image.tmdb.org/t/p/w342/odyssey.jpg',
  genres: [
    { id: 18, name: 'דרמה' },
    { id: 12, name: 'הרפתקאות' },
  ],
  ratings: {
    imdb: { rating: 8.4, votes: 1234567 },
    rotten_tomatoes: 94,
    metacritic: 88,
    tmdb: 8,
  },
  seasons: [],
  stale: false,
  fetched_at: '2026-11-01T10:00:00+00:00',
  posts: [],
  in_wishlist: false,
  taste: null,
}
const SERIES: TitlePageData = {
  ...TITLE,
  media_type: 'series',
  year_end: 2028,
  season_count: 2,
  seasons: [
    {
      season_number: 1,
      name: 'העונה הראשונה',
      name_lang: 'he',
      overview: null,
      air_date: '2026-02-03',
      episode_count: 9,
      poster_url: null,
    },
    {
      season_number: 2,
      name: null,
      name_lang: null,
      overview: null,
      air_date: null,
      episode_count: null,
      poster_url: null,
    },
  ],
}

function renderTitle(api: ReturnType<typeof fakeApi>['api'], route = '/titles/3') {
  return renderApp(
    <Routes>
      <Route path="/titles/:id" element={<TitlePage />} />
    </Routes>,
    { api, route },
  )
}
const serve = (title: TitlePageData, lang = 'he') =>
  fakeApi({ [`GET /titles/3?lang=${lang}`]: title })

describe('TitlePage', () => {
  it('shows details and every rating with its source', async () => {
    renderTitle(serve(TITLE).api)
    expect(await screen.findByRole('heading', { level: 1, name: 'האודיסאה' })).toBeInTheDocument()
    expect(document.querySelector('img')).toHaveAttribute('src', TITLE.poster_url)
    expect(screen.getByText('2026')).toBeInTheDocument()
    expect(screen.getByText('150 דק׳')).toBeInTheDocument()
    expect(screen.getByText('דרמה, הרפתקאות')).toBeInTheDocument()
    expect(screen.getByText('מסע ארוך הביתה.')).toBeInTheDocument()

    const chips = screen.getAllByRole('listitem')
    expect(chips).toHaveLength(4)
    expect(chips[0]).toHaveTextContent('IMDb 8.4')
    expect(chips[0]).toHaveTextContent(new Intl.NumberFormat('he').format(1234567))
    expect(chips[1]).toHaveTextContent('Rotten Tomatoes 94%')
    expect(chips[2]).toHaveTextContent('Metacritic 88')
    expect(chips[3]).toHaveTextContent('TMDB 8.0')
    expect(screen.queryByText(he.title.stale)).not.toBeInTheDocument()
    expect(screen.queryByText(he.lang.en)).not.toBeInTheDocument()
  })

  it('shows series years, seasons and the stale note', async () => {
    renderTitle(serve({ ...SERIES, stale: true }).api)
    expect(await screen.findByText('2026–2028')).toBeInTheDocument()
    expect(screen.getByText(he.title.stale)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: he.title.seasons })).toBeInTheDocument()
    const seasons = screen.getByRole('list', { name: he.title.seasons })
    const [one, two] = within(seasons).getAllByRole('listitem')
    expect(one).toHaveTextContent('העונה הראשונה')
    expect(one).toHaveTextContent('2026')
    expect(one).toHaveTextContent('9 פרקים')
    expect(two).toHaveTextContent('עונה 2')
    expect(two).not.toHaveTextContent('פרקים')
  })

  it("names a season in the UI language, never with TMDB's other-language name", async () => {
    const english = {
      ...SERIES.seasons[1],
      season_number: 3,
      name: 'Season 3',
      name_lang: 'en' as const,
    }
    renderTitle(serve({ ...SERIES, seasons: [...SERIES.seasons, english] }).api)
    const seasons = await screen.findByRole('list', { name: he.title.seasons })
    const third = within(seasons).getAllByRole('listitem')[2]
    expect(third).toHaveTextContent('עונה 3')
    expect(third).not.toHaveTextContent('Season 3')
  })

  it('shows a lone end year without a dangling dash', async () => {
    renderTitle(serve({ ...SERIES, year_start: null }).api)
    expect(await screen.findByText('2028')).toBeInTheDocument()
    expect(screen.queryByText(/–/)).not.toBeInTheDocument()
  })

  it('labels fallback text with its own language', async () => {
    const title = {
      ...TITLE,
      name_lang: 'he',
      overview_lang: 'en',
      overview: 'A long way home.',
    }
    await setLocale('en')
    renderTitle(fakeApi({ 'GET /titles/3?lang=en': title }).api)
    expect(await screen.findByText('A long way home.')).toBeInTheDocument()
    // The name is Hebrew in the English UI: labelled Hebrew. The overview is English: no label.
    expect(screen.getAllByText(en.lang.he)).toHaveLength(1)
    expect(screen.queryByText(en.lang.en)).not.toBeInTheDocument()
  })

  it('shows posts from people you follow under a divider', async () => {
    renderTitle(serve({ ...TITLE, posts: [POST_CARD, { ...POST_CARD, id: 8 }] }).api)
    const heading = await screen.findByRole('heading', {
      name: he.title.fromPeopleYouFollow,
    })
    const separator = screen.getByRole('separator')
    const articles = screen.getAllByRole('article')
    expect(articles).toHaveLength(2)
    expect(separator.compareDocumentPosition(heading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    expect(heading.compareDocumentPosition(articles[0]!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it('shows TMDB reviews in the external part, above the followed-people divider', async () => {
    const fake = fakeApi({
      'GET /titles/3?lang=he': { ...TITLE, posts: [POST_CARD] },
      'GET /titles/3/reviews': { reviews: [EXTERNAL_REVIEW] },
    })
    renderTitle(fake.api)
    const reviews = await screen.findByRole('heading', { name: he.reviews.heading })
    const divider = screen.getByRole('separator')
    expect(reviews.compareDocumentPosition(divider)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it('omits the section when there are no posts', async () => {
    renderTitle(serve(TITLE).api)
    await screen.findByRole('heading', { level: 1 })
    expect(screen.queryByText(he.title.fromPeopleYouFollow)).not.toBeInTheDocument()
    expect(screen.queryByRole('separator')).not.toBeInTheDocument()
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
  })

  it('links Post about this to the composer with the title', async () => {
    renderTitle(serve(TITLE).api)
    expect(await screen.findByRole('link', { name: he.title.postAbout })).toHaveAttribute(
      'href',
      '/post?title=3',
    )
  })

  it('title page saves from search', async () => {
    const fake = fakeApi({
      'GET /titles/3?lang=he': TITLE,
      'POST /wishlist': WISHLIST_ITEM,
    })
    renderTitle(fake.api)
    const post = await screen.findByRole('link', { name: he.title.postAbout })
    const button = screen.getByRole('button', { name: he.wishlist.save })
    expect(button).toHaveAttribute('aria-pressed', 'false')
    expect(post.parentElement).toContainElement(button)
    await userEvent.click(button)
    expect(fake.calls).toHaveBeenCalledWith('/wishlist', {
      method: 'POST',
      body: { title_id: 3, source: 'search' },
    })
  })

  it('saves from Discover with source discover', async () => {
    const fake = fakeApi({
      'GET /titles/3?lang=he': TITLE,
      'POST /wishlist': WISHLIST_ITEM,
    })
    renderTitle(fake.api, '/titles/3?via=discover')
    await userEvent.click(await screen.findByRole('button', { name: he.wishlist.save }))
    expect(fake.calls).toHaveBeenCalledWith('/wishlist', {
      method: 'POST',
      body: { title_id: 3, source: 'discover' },
    })
  })

  it('ignores an unknown via', async () => {
    const fake = fakeApi({
      'GET /titles/3?lang=he': TITLE,
      'POST /wishlist': WISHLIST_ITEM,
    })
    renderTitle(fake.api, '/titles/3?via=feed')
    await userEvent.click(await screen.findByRole('button', { name: he.wishlist.save }))
    expect(fake.calls).toHaveBeenCalledWith('/wishlist', {
      method: 'POST',
      body: { title_id: 3, source: 'search' },
    })
  })

  it('shows Saved when the title is on your wishlist', async () => {
    renderTitle(serve({ ...TITLE, in_wishlist: true }).api)
    expect(await screen.findByRole('button', { name: he.wishlist.saved })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('unknown title shows Not found', async () => {
    const api = fakeApi({
      'GET /titles/3?lang=he': () => Promise.reject(new ApiError(404, 'not_found')),
    }).api
    renderTitle(api)
    expect(await screen.findByRole('heading', { name: he.notFound.title })).toBeInTheDocument()
  })

  it('shows Not found for a malformed id without calling the API', async () => {
    const fake = fakeApi({})
    renderTitle(fake.api, '/titles/abc')
    expect(await screen.findByRole('heading', { name: he.notFound.title })).toBeInTheDocument()
    expect(fake.calls).not.toHaveBeenCalled()
  })

  it('offers a retry when the catalogue is unavailable', async () => {
    let fail = true
    const api = fakeApi({
      'GET /titles/3?lang=he': () => {
        if (fail) throw new ApiError(503, 'catalog_unavailable')
        return TITLE
      },
    }).api
    renderTitle(api)
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    fail = false
    await userEvent.click(screen.getByRole('button', { name: he.common.retry }))
    expect(await screen.findByRole('heading', { level: 1, name: 'האודיסאה' })).toBeInTheDocument()
  })
})

describe('ExternalRatings', () => {
  it('renders a chip only for the sources that are present', () => {
    renderApp(
      <ExternalRatings
        ratings={{
          imdb: { rating: 7, votes: null },
          rotten_tomatoes: null,
          metacritic: null,
          tmdb: 6.5,
        }}
      />,
    )
    const chips = screen.getAllByRole('listitem')
    expect(chips).toHaveLength(2)
    expect(chips[0]).toHaveTextContent(/^IMDb 7\.0$/)
    expect(chips[1]).toHaveTextContent('TMDB 6.5')
  })

  it('renders nothing when no source has a rating', () => {
    renderApp(
      <ExternalRatings
        ratings={{
          imdb: null,
          rotten_tomatoes: null,
          metacritic: null,
          tmdb: null,
        }}
      />,
    )
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('shows the title score without an agreement', async () => {
    await setLocale('en')
    renderTitle(
      serve({ ...TITLE, taste: { fit: 79, genres: ['Drama'], agreement: null } }, 'en').api,
    )
    const line = await screen.findByTestId('taste-line')
    expect(line.textContent?.replace(/\s+/g, ' ')).toBe('79% match · Drama fits you')
    expect(line).not.toHaveTextContent('agree')
  })

  it('shows no Taste Match line when the score is locked', async () => {
    renderTitle(serve(TITLE).api)
    await screen.findByRole('heading', { level: 1, name: 'האודיסאה' })
    expect(screen.queryByTestId('taste-line')).not.toBeInTheDocument()
  })
})
