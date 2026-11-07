import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { initI18n, setLocale } from '../i18n'
import en from '../i18n/en.json'
import he from '../i18n/he.json'
import { PostCard } from '../posts/PostCard'
import { fakeApi, POST_CARD, WISHLIST_ITEM } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { SaveButton } from './SaveButton'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const SAVE = { name: he.wishlist.save }
const SAVED = { name: he.wishlist.saved }

describe('SaveButton', () => {
  it('has the exact labels in Hebrew and English', () => {
    expect([he.wishlist.save, he.wishlist.saved]).toEqual(['שמירה לרשימה', 'נשמר ברשימה'])
    expect([en.wishlist.save, en.wishlist.saved]).toEqual(['Save to wishlist', 'Saved'])
  })

  it("saves a post's title with its source post", async () => {
    const fake = fakeApi({ 'POST /wishlist': WISHLIST_ITEM })
    renderApp(<PostCard post={POST_CARD} />, { api: fake.api })
    const button = screen.getByRole('button', SAVE)
    expect(button).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(button)
    expect(await screen.findByRole('button', SAVED)).toHaveAttribute('aria-pressed', 'true')
    expect(fake.calls).toHaveBeenCalledWith('/wishlist', {
      method: 'POST',
      body: { title_id: 3, source: 'post', source_post_id: 7 },
    })
  })

  it('pressing Saved removes it', async () => {
    const fake = fakeApi({ 'DELETE /wishlist/3': null })
    renderApp(<PostCard post={{ ...POST_CARD, in_wishlist: true }} />, { api: fake.api })
    const button = screen.getByRole('button', SAVED)
    expect(button).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(button)
    expect(await screen.findByRole('button', SAVE)).toHaveAttribute('aria-pressed', 'false')
    expect(fake.log()).toEqual(['DELETE /wishlist/3'])
  })

  it('hides Save on your own post', () => {
    const own = { ...POST_CARD, author: { ...POST_CARD.author, follow_state: 'self' as const } }
    renderApp(<PostCard post={own} />, { api: fakeApi({}).api })
    expect(screen.queryByRole('button', SAVE)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', SAVED)).not.toBeInTheDocument()
  })

  it('shows an error when saving fails', async () => {
    const fake = fakeApi({
      'POST /wishlist': () => {
        throw new ApiError(503, 'unavailable')
      },
    })
    renderApp(<SaveButton titleId={3} saved={false} source="search" />, { api: fake.api })
    await userEvent.click(screen.getByRole('button', SAVE))
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    expect(screen.getByRole('button', SAVE)).toBeEnabled()
    expect(screen.getByRole('button', SAVE)).toHaveAttribute('aria-pressed', 'false')
  })

  it('does not pretend a title is saved when its source post is gone (404)', async () => {
    const fake = fakeApi({
      'POST /wishlist': () => {
        throw new ApiError(404, 'not_found')
      },
    })
    renderApp(<PostCard post={POST_CARD} />, { api: fake.api })
    await userEvent.click(screen.getByRole('button', SAVE))
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    expect(screen.getByRole('button', SAVE)).toHaveAttribute('aria-pressed', 'false')
  })

  it('is disabled while the request is on its way', async () => {
    let finish: (value: unknown) => void = () => {}
    const fake = fakeApi({ 'POST /wishlist': () => new Promise((resolve) => (finish = resolve)) })
    renderApp(<SaveButton titleId={3} saved={false} source="search" />, { api: fake.api })
    await userEvent.click(screen.getByRole('button', SAVE))
    expect(await screen.findByRole('button')).toBeDisabled()
    finish(WISHLIST_ITEM)
    expect(await screen.findByRole('button', SAVED)).toBeEnabled()
  })

  it('refetches posts, titles and the wishlist after a change', async () => {
    const fake = fakeApi({ 'POST /wishlist': WISHLIST_ITEM })
    const { client } = renderApp(<SaveButton titleId={3} saved={false} source="search" />, {
      api: fake.api,
    })
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    await userEvent.click(screen.getByRole('button', SAVE))
    await screen.findByRole('button', SAVED)
    const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey)
    expect(keys).toEqual(expect.arrayContaining([['wishlist'], ['posts'], ['title']]))
  })
})
