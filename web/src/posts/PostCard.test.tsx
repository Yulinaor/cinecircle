import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { PostCard as PostCardData } from '../api/types'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
import he from '../i18n/he.json'
import { POST_CARD } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { PostCard } from './PostCard'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const show = (post: PostCardData) => renderApp(<PostCard post={post} />)
const withTitle = (changes: Partial<PostCardData['title']>): PostCardData => ({
  ...POST_CARD,
  title: { ...POST_CARD.title, ...changes },
})
const AS_OTHER: PostCardData = {
  ...POST_CARD,
  opinion: 'הרוצח הוא הדוור',
  contains_spoilers: true,
}
const AS_AUTHOR: PostCardData = { ...AS_OTHER, author: { ...POST_CARD.author, follow_state: 'self' } }

describe('PostCard', () => {
  it('shows rating, title, season, meta and IMDb', () => {
    show({
      ...POST_CARD,
      title: { ...POST_CARD.title, media_type: 'series' },
      season: {
        number: 2,
        name: null,
        name_lang: null,
        overview: null,
        overview_lang: null,
        poster_url: 'https://image.tmdb.org/t/p/w342/season2.jpg',
      },
    })
    expect(screen.getByText('9.0')).toBeInTheDocument()
    expect(screen.getByText(he.post.outOf)).toBeInTheDocument()
    const name = screen.getByRole('link', { name: 'האודיסאה' })
    expect(name).toHaveAttribute('href', '/titles/3')
    expect(screen.getByText('עונה 2')).toBeInTheDocument()
    expect(screen.getByText('2026')).toBeInTheDocument()
    expect(screen.getByText('150 דק׳')).toBeInTheDocument()
    expect(screen.getByText('דרמה, הרפתקאות')).toBeInTheDocument()
    expect(screen.getByText(/IMDb/)).toHaveTextContent('IMDb 8.4')
    expect(screen.getByText('מסע ארוך הביתה.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Dana/ })).toHaveAttribute('href', '/u/dana')
    expect(screen.getByText('@dana')).toBeInTheDocument()
    expect(document.querySelector('img')).toHaveAttribute(
      'src',
      'https://image.tmdb.org/t/p/w342/season2.jpg',
    )
  })

  it("uses the season's name when it has one, and the title poster when the season has none", () => {
    show({
      ...POST_CARD,
      title: { ...POST_CARD.title, media_type: 'series' },
      season: {
        number: 1,
        name: 'העונה הראשונה',
        name_lang: 'he',
        overview: 'פרק הפתיחה.',
        overview_lang: 'he',
        poster_url: null,
      },
    })
    expect(screen.getByText('העונה הראשונה')).toBeInTheDocument()
    expect(screen.getByText('פרק הפתיחה.')).toBeInTheDocument()
    expect(document.querySelector('img')).toHaveAttribute('src', POST_CARD.title.poster_url)
  })

  it('keeps the score and "/10" in one left-to-right run', () => {
    show(POST_CARD)
    const run = screen.getByText('9.0').closest('[dir="ltr"]')
    expect(run).not.toBeNull()
    expect(run).toHaveTextContent('9.0/10')
  })

  it("shows TMDB's season name only when it is in the UI language", async () => {
    const series = (name_lang: 'he' | 'en'): PostCardData => ({
      ...POST_CARD,
      title: { ...POST_CARD.title, media_type: 'series' },
      season: {
        number: 1,
        name: name_lang === 'he' ? 'עונה ראשונה' : 'Season One',
        name_lang,
        overview: null,
        overview_lang: null,
        poster_url: null,
      },
    })
    const { unmount } = show(series('en'))
    expect(screen.getByText('עונה 1')).toBeInTheDocument()
    expect(screen.queryByText('Season One')).not.toBeInTheDocument()
    unmount()

    await setLocale('en')
    const again = show(series('he'))
    expect(screen.getByText('Season 1')).toBeInTheDocument()
    again.unmount()
    show(series('en'))
    expect(screen.getByText('Season One')).toBeInTheDocument()
  })

  it('names a post on a whole series, and shows a placeholder without any poster', () => {
    show(withTitle({ media_type: 'series', poster_url: null }))
    expect(screen.getByText(he.post.wholeSeries)).toBeInTheDocument()
    expect(screen.getByTestId('poster-placeholder')).toBeInTheDocument()
    expect(document.querySelector('img')).toBeNull()
  })

  it('labels English fallback text', () => {
    show(withTitle({ overview: 'A long way home.', overview_lang: 'en' }))
    expect(screen.getByText('A long way home.')).toBeInTheDocument()
    expect(screen.getByText(he.lang.en)).toBeInTheDocument()
  })

  it('names the actual language of a Hebrew fallback in the English UI', async () => {
    await setLocale('en')
    show(withTitle({ overview: 'מסע ארוך הביתה.', overview_lang: 'he' }))
    expect(screen.getByText('מסע ארוך הביתה.')).toBeInTheDocument()
    expect(screen.getByText(en.lang.he)).toHaveTextContent('Hebrew')
    expect(screen.queryByText(en.lang.en)).not.toBeInTheDocument()
  })

  it('does not label text that is in the UI language', () => {
    show(POST_CARD)
    expect(screen.queryByText(he.lang.en)).not.toBeInTheDocument()
  })

  it('hides spoilers until asked, except for the author', async () => {
    const { unmount } = show(AS_OTHER)
    expect(screen.queryByText('הרוצח הוא הדוור')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: he.post.showSpoiler }))
    expect(screen.getByText('הרוצח הוא הדוור')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: he.post.showSpoiler })).not.toBeInTheDocument()
    unmount()

    show(AS_AUTHOR)
    expect(screen.getByText('הרוצח הוא הדוור')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: he.post.showSpoiler })).not.toBeInTheDocument()
  })

  it('marks private and edited posts and links Edit for the author only', () => {
    const { unmount } = show(POST_CARD)
    expect(screen.queryByText(he.post.private)).not.toBeInTheDocument()
    expect(screen.queryByText(he.post.edited)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: he.post.edit })).not.toBeInTheDocument()
    unmount()

    const other = show({ ...POST_CARD, is_shared: false, edited: true })
    expect(screen.getByText(he.post.private)).toBeInTheDocument()
    expect(screen.getByText(he.post.edited)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: he.post.edit })).not.toBeInTheDocument()
    other.unmount()

    show({ ...POST_CARD, author: { ...POST_CARD.author, follow_state: 'self' } })
    expect(screen.getByRole('link', { name: he.post.edit })).toHaveAttribute('href', '/posts/7/edit')
  })

  it('falls back to the TMDB rating labelled TMDB', () => {
    show(withTitle({ imdb_rating: null }))
    expect(screen.getByText(/TMDB/)).toHaveTextContent('TMDB 8.0')
    expect(screen.queryByText(/IMDb/)).not.toBeInTheDocument()
  })

  it('shows no ratings line when the title has neither rating', () => {
    show(withTitle({ imdb_rating: null, tmdb_rating: null }))
    const card = screen.getByRole('article')
    expect(within(card).queryByText(/IMDb|TMDB/)).not.toBeInTheDocument()
  })

  it('offers Save to the viewer, reflecting their own wishlist, but not to the author', () => {
    const { unmount } = show(POST_CARD)
    expect(screen.getByRole('button', { name: he.wishlist.save })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    unmount()

    const saved = show({ ...POST_CARD, in_wishlist: true })
    expect(screen.getByRole('button', { name: he.wishlist.saved })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    saved.unmount()

    show(AS_AUTHOR)
    expect(screen.queryByRole('button', { name: he.wishlist.save })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: he.wishlist.saved })).not.toBeInTheDocument()
  })
})
