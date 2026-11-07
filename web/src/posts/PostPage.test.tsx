import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { AppRoutes } from '../app/routes'
import { initI18n, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { fakeApi, POST_CARD } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { PostPage } from './PostPage'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

function renderPost(api: ReturnType<typeof fakeApi>['api'], route = '/posts/7') {
  return renderApp(
    <Routes>
      <Route path="/posts/:id" element={<PostPage />} />
    </Routes>,
    { api, route },
  )
}

describe('PostPage', () => {
  it('shows the post in the UI language', async () => {
    const fake = fakeApi({ 'GET /posts/7?lang=he': POST_CARD })
    renderPost(fake.api)
    expect(await screen.findByRole('link', { name: 'האודיסאה' })).toBeInTheDocument()
    expect(screen.getByText('סרט מדהים')).toBeInTheDocument()
  })

  it('post page shows Not found for a hidden post', async () => {
    const fake = fakeApi({ 'GET /posts/7?lang=he': () => Promise.reject(new ApiError(404, 'not_found')) })
    renderPost(fake.api)
    expect(await screen.findByRole('heading', { name: he.notFound.title })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: he.notFound.home })).toHaveAttribute('href', '/')
  })

  it('shows Not found for a malformed id without calling the API', async () => {
    const fake = fakeApi({})
    renderPost(fake.api, '/posts/abc')
    expect(await screen.findByRole('heading', { name: he.notFound.title })).toBeInTheDocument()
    expect(fake.calls).not.toHaveBeenCalled()
  })

  it('offers a retry on other errors', async () => {
    let fail = true
    const fake = fakeApi({
      'GET /posts/7?lang=he': () => {
        if (fail) throw new ApiError(503, 'db_unavailable')
        return POST_CARD
      },
    })
    renderPost(fake.api)
    expect(await screen.findByRole('alert')).toHaveTextContent(he.common.error)
    fail = false
    await userEvent.click(screen.getByRole('button', { name: he.common.retry }))
    expect(await screen.findByRole('link', { name: 'האודיסאה' })).toBeInTheDocument()
  })
})

describe('routes', () => {
  it('unknown route shows Not found', () => {
    renderApp(<AppRoutes />, { api: fakeApi({}).api, route: '/no/such/page' })
    expect(screen.getByRole('heading', { name: he.notFound.title })).toBeInTheDocument()
  })
})
