import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { ExternalReview } from '../api/types'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
import he from '../i18n/he.json'
import { EXTERNAL_REVIEW as REVIEW, fakeApi } from '../test/fakeApi'
import { findPhysicalUtilities } from '../test/rtl'
import { renderApp } from '../test/renderApp'
import { ExternalReviews } from './ExternalReviews'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('en')
})

const serve = (reviews: ExternalReview[]) => fakeApi({ 'GET /titles/3/reviews': { reviews } })

describe('ExternalReviews', () => {
  it('renders reviews as attributed plain text', async () => {
    renderApp(<ExternalReviews titleId={3} />, { api: serve([REVIEW]).api })
    expect(await screen.findByRole('heading', { name: en.reviews.heading })).toBeInTheDocument()
    const card = screen.getByRole('article')
    expect(card).toHaveTextContent('Review by jdoe on TMDB')
    expect(card).toHaveTextContent('Rated 7.5/10')
    // The excerpt is text: the markup-looking part shows literally and creates no element.
    expect(within(card).getByText('A <b>x</b> film that stays with you.')).toHaveAttribute(
      'dir',
      'auto',
    )
    expect(card.querySelector('b')).toBeNull()
    const link = within(card).getByRole('link', { name: en.reviews.read })
    expect(link).toHaveAttribute('href', REVIEW.url)
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    expect(card.querySelector('bdi[dir="auto"]')).toHaveTextContent('jdoe')
  })

  it('uses the Hebrew wording in Hebrew', async () => {
    await setLocale('he')
    renderApp(<ExternalReviews titleId={3} />, { api: serve([REVIEW]).api })
    const card = await screen.findByRole('article')
    expect(card).toHaveTextContent('ביקורת של jdoe ב־TMDB')
    expect(card).toHaveTextContent('דירג/ה 7.5/10')
    expect(within(card).getByRole('link', { name: he.reviews.read })).toBeInTheDocument()
  })

  it('omits the rating when the review has none', async () => {
    renderApp(<ExternalReviews titleId={3} />, {
      api: serve([{ ...REVIEW, author_rating: null }]).api,
    })
    const card = await screen.findByRole('article')
    expect(card).not.toHaveTextContent(/Rated/)
  })

  it('shows no avatar or follow control in reviews', async () => {
    renderApp(<ExternalReviews titleId={3} />, { api: serve([REVIEW, REVIEW]).api })
    const cards = await screen.findAllByRole('article')
    expect(cards).toHaveLength(2)
    for (const card of cards) {
      expect(card.querySelector('img')).toBeNull()
      expect(within(card).queryByRole('button')).toBeNull()
      expect(within(card).getAllByRole('link')).toHaveLength(1)
    }
  })

  it('shows nothing when there are no reviews', async () => {
    const fake = serve([])
    const { container } = renderApp(<ExternalReviews titleId={3} />, { api: fake.api })
    await vi.waitFor(() => expect(fake.count('GET /titles/3/reviews')).toBe(1))
    await vi.waitFor(() => expect(container).toBeEmptyDOMElement())
    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  })

  it('shows nothing when the request fails', async () => {
    const fake = fakeApi({
      'GET /titles/3/reviews': () => {
        throw new ApiError(404, 'not_found')
      },
    })
    const { container } = renderApp(<ExternalReviews titleId={3} />, { api: fake.api })
    await vi.waitFor(() => expect(fake.count('GET /titles/3/reviews')).toBe(1))
    expect(container).toBeEmptyDOMElement()
  })

  it('uses logical utilities only', () => {
    const sources = import.meta.glob<string>(['./ExternalReviews.tsx', '../me/About.tsx'], {
      query: '?raw',
      import: 'default',
      eager: true,
    })
    expect(Object.keys(sources)).toHaveLength(2)
    expect(Object.values(sources).flatMap((source) => findPhysicalUtilities(source))).toEqual([])
  })
})
