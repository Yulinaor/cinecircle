import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useLocation } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { initI18n, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { fakeApi, quizTitleRoutes } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { DiscoverTitleRedirect } from './DiscoverTitleRedirect'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

function Landing() {
  const { pathname, search } = useLocation()
  return <p>{`landed ${pathname}${search}`}</p>
}

function renderRedirect(api: ReturnType<typeof fakeApi>['api'], route: string) {
  return renderApp(
    <Routes>
      <Route path="/discover/t/:mediaType/:tmdbId" element={<DiscoverTitleRedirect />} />
      <Route path="/titles/:id" element={<Landing />} />
    </Routes>,
    { api, route },
  )
}

const MATRIX = { ...quizTitleRoutes()['GET /titles/tmdb/movie/278?lang=he']!, id: 7, tmdb_id: 603 }

describe('DiscoverTitleRedirect', () => {
  it('resolves a TMDB id to the title page', async () => {
    const fake = fakeApi({ 'GET /titles/tmdb/movie/603?lang=he': MATRIX })
    renderRedirect(fake.api, '/discover/t/movie/603')
    expect(await screen.findByText('landed /titles/7?via=discover')).toBeInTheDocument()
    expect(fake.log()).toEqual(['GET /titles/tmdb/movie/603?lang=he'])
  })

  it('resolves a series', async () => {
    const fake = fakeApi({ 'GET /titles/tmdb/series/1396?lang=he': { ...MATRIX, id: 9 } })
    renderRedirect(fake.api, '/discover/t/series/1396')
    expect(await screen.findByText('landed /titles/9?via=discover')).toBeInTheDocument()
  })

  it('shows Not found for a missing title', async () => {
    renderRedirect(fakeApi({}).api, '/discover/t/movie/603')
    expect(await screen.findByRole('heading', { name: he.notFound.title })).toBeInTheDocument()
  })

  it.each(['/discover/t/book/603', '/discover/t/movie/abc', '/discover/t/movie/0'])(
    'shows Not found for %s without calling the API',
    async (route) => {
      const fake = fakeApi({})
      renderRedirect(fake.api, route)
      expect(await screen.findByRole('heading', { name: he.notFound.title })).toBeInTheDocument()
      expect(fake.calls).not.toHaveBeenCalled()
    },
  )

  it('explains and retries when the catalogue is unavailable', async () => {
    let fail = true
    const api = fakeApi({
      'GET /titles/tmdb/movie/603?lang=he': () => {
        if (fail) throw new ApiError(503, 'catalog_unavailable')
        return MATRIX
      },
    }).api
    renderRedirect(api, '/discover/t/movie/603')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      he.compose.errors.catalog_unavailable,
    )
    fail = false
    await userEvent.click(screen.getByRole('button', { name: he.common.retry }))
    expect(await screen.findByText('landed /titles/7?via=discover')).toBeInTheDocument()
  })
})
