import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { PostCard, PostPage } from '../api/types'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
import he from '../i18n/he.json'
import { POST_CARD, fakeApi } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { HomePage } from './HomePage'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const post = (id: number, name: string): PostCard => ({
  ...POST_CARD,
  id,
  title: { ...POST_CARD.title, name },
})
const page = (posts: PostCard[], next_cursor: string | null = null): PostPage => ({
  posts,
  next_cursor,
})

describe('HomePage', () => {
  it('shows the feed newest first', async () => {
    const fake = fakeApi({
      'GET /feed?type=all&lang=he': page([post(2, 'סרט חדש'), post(1, 'סרט ישן')]),
    })
    renderApp(<HomePage />, { api: fake.api })
    const cards = await screen.findAllByRole('article')
    expect(cards).toHaveLength(2)
    expect(within(cards[0]!).getByText('סרט חדש')).toBeInTheDocument()
    expect(within(cards[1]!).getByText('סרט ישן')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: he.feed.filter.all })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('filters by Movies and Series', async () => {
    const fake = fakeApi({
      'GET /feed?type=all&lang=he': page([post(1, 'סרט')]),
      'GET /feed?type=movie&lang=he': page([post(1, 'סרט')]),
      'GET /feed?type=series&lang=he': page([post(5, 'סדרה')]),
    })
    renderApp(<HomePage />, { api: fake.api })
    await screen.findByText('סרט')
    await userEvent.click(screen.getByRole('button', { name: he.feed.filter.series }))
    expect(await screen.findByText('סדרה')).toBeInTheDocument()
    expect(fake.log()).toContain('GET /feed?type=series&lang=he')
    expect(screen.getByRole('button', { name: he.feed.filter.series })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: he.feed.filter.all })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    await userEvent.click(screen.getByRole('button', { name: he.feed.filter.movie }))
    await vi.waitFor(() => expect(fake.log()).toContain('GET /feed?type=movie&lang=he'))
  })

  it('loads the next page with the cursor', async () => {
    const fake = fakeApi({
      'GET /feed?type=all&lang=he': page([post(3, 'שלישי'), post(2, 'שני')], 'c1'),
      'GET /feed?type=all&lang=he&cursor=c1': page([post(1, 'ראשון')]),
    })
    renderApp(<HomePage />, { api: fake.api })
    await screen.findByText('שלישי')
    await userEvent.click(screen.getByRole('button', { name: he.common.loadMore }))
    expect(await screen.findByText('ראשון')).toBeInTheDocument()
    expect(screen.getAllByRole('article')).toHaveLength(3)
    expect(screen.queryByRole('button', { name: he.common.loadMore })).not.toBeInTheDocument()
  })

  it('shows the empty state with a way to find people', async () => {
    const fake = fakeApi({ 'GET /feed?type=all&lang=he': page([]) })
    renderApp(<HomePage />, { api: fake.api })
    expect(await screen.findByText(he.feed.empty)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: he.feed.findPeople })).toHaveAttribute(
      'href',
      '/people',
    )
    expect(screen.getByRole('link', { name: he.feed.createPost })).toHaveAttribute('href', '/post')
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
  })

  it('refetches in English when the language changes', async () => {
    const fake = fakeApi({
      'GET /feed?type=all&lang=he': page([post(1, 'האודיסאה')]),
      'GET /feed?type=all&lang=en': page([post(1, 'The Odyssey')]),
    })
    renderApp(<HomePage />, { api: fake.api })
    await screen.findByText('האודיסאה')
    await act(() => setLocale('en'))
    expect(await screen.findByText('The Odyssey')).toBeInTheDocument()
    expect(fake.log()).toContain('GET /feed?type=all&lang=en')
    expect(screen.getByRole('button', { name: en.feed.filter.all })).toBeInTheDocument()
  })

  it('keeps loaded posts when loading more fails', async () => {
    let failNext = true
    const fake = fakeApi({
      'GET /feed?type=all&lang=he': page([post(2, 'שני'), post(1, 'ראשון')], 'c1'),
      'GET /feed?type=all&lang=he&cursor=c1': () => {
        if (failNext) throw new ApiError(500, 'boom')
        return page([post(0, 'אפס')])
      },
    })
    renderApp(<HomePage />, { api: fake.api })
    await screen.findByText('שני')
    await userEvent.click(screen.getByRole('button', { name: he.common.loadMore }))
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    expect(screen.getAllByRole('article')).toHaveLength(2)
    failNext = false
    await userEvent.click(screen.getByRole('button', { name: he.common.retry }))
    expect(await screen.findByText('אפס')).toBeInTheDocument()
    expect(screen.getAllByRole('article')).toHaveLength(3)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows a full-page error with retry when nothing loaded', async () => {
    let fail = true
    const fake = fakeApi({
      'GET /feed?type=all&lang=he': () => {
        if (fail) throw new ApiError(500, 'boom')
        return page([post(1, 'ראשון')])
      },
    })
    renderApp(<HomePage />, { api: fake.api })
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    fail = false
    await userEvent.click(screen.getByRole('button', { name: he.common.retry }))
    expect(await screen.findByText('ראשון')).toBeInTheDocument()
  })

  describe('taste unlock hint', () => {
    const meWith = (taste_unlocked: boolean) => ({
      id: 'user-1',
      email: null,
      profile: null,
      taste_unlocked,
    })

    it('invites a locked user to the quiz', async () => {
      const fake = fakeApi({
        'GET /feed?type=all&lang=he': page([]),
        'GET /me': meWith(false),
      })
      renderApp(<HomePage />, { api: fake.api })
      expect(await screen.findByText(he.taste.unlock)).toBeInTheDocument()
      expect(screen.getByRole('link', { name: he.taste.unlockCta })).toHaveAttribute(
        'href',
        '/taste',
      )
    })

    it('shows no hint once unlocked', async () => {
      const fake = fakeApi({
        'GET /feed?type=all&lang=he': page([]),
        'GET /me': meWith(true),
      })
      renderApp(<HomePage />, { api: fake.api })
      await screen.findByText(he.feed.empty)
      await vi.waitFor(() => expect(fake.log()).toContain('GET /me'))
      expect(screen.queryByText(he.taste.unlock)).not.toBeInTheDocument()
      expect(screen.queryByRole('link', { name: he.taste.unlockCta })).not.toBeInTheDocument()
    })

    it('shows no hint before the account has loaded', async () => {
      const fake = fakeApi({ 'GET /feed?type=all&lang=he': page([]) })
      renderApp(<HomePage />, { api: fake.api })
      await screen.findByText(he.feed.empty)
      expect(screen.queryByText(he.taste.unlock)).not.toBeInTheDocument()
    })
  })
})
