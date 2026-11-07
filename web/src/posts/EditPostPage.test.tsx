import { fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { PostCard } from '../api/types'
import { initI18n, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { fakeApi, POST_CARD, type FakeRoute } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { EditPostPage } from './EditPostPage'

vi.mock('../auth/supabase', () => ({ supabase: null }))

// delay: null skips the per-keystroke setTimeout(0), which is slow under parallel load.
const typist = userEvent.setup({ delay: null })

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const MINE: PostCard = {
  ...POST_CARD,
  id: 5,
  author: { ...POST_CARD.author, follow_state: 'self' },
  rating: 8,
  opinion: 'Great',
}

function setup(routes: Record<string, FakeRoute>, route = '/posts/5/edit') {
  const fake = fakeApi({ 'GET /posts/5?lang=he': MINE, ...routes })
  const view = renderApp(
    <Routes>
      <Route path="/posts/:id/edit" element={<EditPostPage />} />
      <Route
        path="/posts/:id"
        element={
          <>
            <p>POST PAGE</p>
            <Link to="/posts/5/edit">again</Link>
          </>
        }
      />
      <Route path="/profile" element={<p>PROFILE</p>} />
    </Routes>,
    { api: fake.api, route },
  )
  return { fake, ...view }
}

const save = () => screen.findByRole('button', { name: he.compose.save })
const bodyOf = (fake: ReturnType<typeof setup>['fake'], key: string) =>
  (
    fake.calls.mock.calls.find(
      ([path, init]) =>
        `${(init as { method?: string } | undefined)?.method ?? 'GET'} ${path}` === key,
    )?.[1] as { body?: unknown } | undefined
  )?.body

describe('EditPostPage', () => {
  it('shows the title read-only and the form prefilled', async () => {
    setup({})
    await save()
    expect(screen.getByRole('link', { name: 'האודיסאה' })).toHaveAttribute('href', '/titles/3')
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('radiogroup', { name: he.compose.season })).not.toBeInTheDocument()
    expect(screen.getByRole('slider')).toHaveAttribute('aria-valuetext', '8.0')
    expect(screen.getByLabelText(he.compose.opinion)).toHaveValue('Great')
    expect(screen.getByRole('radio', { name: he.compose.share })).toBeChecked()
  })

  it('edits only changed fields and deletes after confirming', async () => {
    const { fake, client } = setup({
      'PATCH /posts/5': { ...MINE, rating: 8.5, edited: true },
      'DELETE /posts/5': null,
    })
    const invalidate = vi.spyOn(client, 'invalidateQueries')

    await typist.click(await screen.findByRole('button', { name: he.compose.increase }))
    await typist.click(await save())
    expect(await screen.findByText('POST PAGE')).toBeInTheDocument()
    expect(bodyOf(fake, 'PATCH /posts/5')).toEqual({ rating: 8.5 })
    const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey)
    // The wishlist shows your rating on a title, so it refetches too.
    expect(keys).toEqual(
      expect.arrayContaining([['posts'], ['title'], ['profile'], ['wishlist']]),
    )

    // Back to the editor: delete asks first, then goes to the profile.
    await typist.click(screen.getByRole('link', { name: 'again' }))
    await typist.click(await screen.findByRole('button', { name: he.compose.delete }))
    expect(screen.getByText(he.compose.confirmDelete)).toBeInTheDocument()
    expect(fake.count('DELETE /posts/5')).toBe(0)
    invalidate.mockClear()
    await typist.click(screen.getByRole('button', { name: he.compose.yes }))
    expect(await screen.findByText('PROFILE')).toBeInTheDocument()
    expect(fake.count('DELETE /posts/5')).toBe(1)
    // A deleted post is no longer "Your rating" on the wishlist.
    expect(invalidate.mock.calls.map(([filters]) => filters?.queryKey)).toContainEqual(['wishlist'])
  })

  it('Cancel keeps the post', async () => {
    const { fake } = setup({})
    await typist.click(await screen.findByRole('button', { name: he.compose.delete }))
    await typist.click(screen.getByRole('button', { name: he.compose.cancel }))
    expect(screen.queryByText(he.compose.confirmDelete)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: he.compose.delete })).toBeInTheDocument()
    expect(fake.count('DELETE /posts/5')).toBe(0)
  })

  it('shows an error when deleting fails and stays on the page', async () => {
    setup({
      'DELETE /posts/5': () => {
        throw new ApiError(503, 'db_unavailable')
      },
    })
    await typist.click(await screen.findByRole('button', { name: he.compose.delete }))
    await typist.click(screen.getByRole('button', { name: he.compose.yes }))
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    expect(screen.queryByText('PROFILE')).not.toBeInTheDocument()
  })

  it('sends a cleared opinion as null and the other changed fields', async () => {
    const { fake } = setup({ 'PATCH /posts/5': MINE })
    await save()
    fireEvent.change(screen.getByLabelText(he.compose.opinion), { target: { value: '  ' } })
    await typist.click(screen.getByRole('checkbox', { name: he.compose.spoiler }))
    await typist.click(screen.getByRole('radio', { name: he.compose.keepPrivate }))
    await typist.click(await save())
    await screen.findByText('POST PAGE')
    expect(bodyOf(fake, 'PATCH /posts/5')).toEqual({
      opinion: null,
      contains_spoilers: true,
      is_shared: false,
    })
  })

  it('saving without changes sends nothing', async () => {
    const { fake } = setup({})
    await typist.click(await save())
    expect(await screen.findByText('POST PAGE')).toBeInTheDocument()
    expect(fake.log()).toEqual(['GET /posts/5?lang=he'])
  })

  it('keeps an over-long opinion from being saved', async () => {
    setup({})
    await save()
    fireEvent.change(screen.getByLabelText(he.compose.opinion), {
      target: { value: 'x'.repeat(501) },
    })
    expect(await save()).toBeDisabled()
  })

  it('shows Not found for someone else’s post', async () => {
    const { fake } = setup({ 'GET /posts/5?lang=he': POST_CARD })
    expect(await screen.findByRole('heading', { name: he.notFound.title })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: he.compose.save })).not.toBeInTheDocument()
    expect(fake.log()).toEqual(['GET /posts/5?lang=he'])
  })

  it('shows Not found for a missing post', async () => {
    setup({ 'GET /posts/5?lang=he': () => Promise.reject(new ApiError(404, 'not_found')) })
    expect(await screen.findByRole('heading', { name: he.notFound.title })).toBeInTheDocument()
  })

  it('shows Not found for a malformed id without calling the API', async () => {
    const { fake } = setup({}, '/posts/abc/edit')
    expect(await screen.findByRole('heading', { name: he.notFound.title })).toBeInTheDocument()
    expect(fake.calls).not.toHaveBeenCalled()
  })

  it('shows an error when saving fails and lets you retry', async () => {
    let fail = true
    const { fake } = setup({
      'PATCH /posts/5': () => {
        if (fail) throw new ApiError(503, 'db_unavailable')
        return MINE
      },
    })
    await typist.click(await screen.findByRole('button', { name: he.compose.increase }))
    await typist.click(await save())
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    fail = false
    await typist.click(await save())
    expect(await screen.findByText('POST PAGE')).toBeInTheDocument()
    expect(fake.count('PATCH /posts/5')).toBe(2)
  })
})
