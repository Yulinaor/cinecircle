import { act, fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { initI18n, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { DANA, fakeApi } from '../test/fakeApi'
import { renderApp } from '../test/renderApp'
import { PeopleSearchPage } from './PeopleSearchPage'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

function setup(results: unknown[] = [DANA]) {
  const fake = fakeApi({
    'GET /users/search?q=ga': { results },
    'GET /users/search?q=gal': { results },
  })
  renderApp(<PeopleSearchPage />, { api: fake.api })
  const input = screen.getByRole('searchbox', { name: he.people.search })
  // fireEvent, not userEvent: Testing Library's async wrapper can't see vitest's fake timers.
  const type = (value: string) => fireEvent.change(input, { target: { value } })
  const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms))
  return { fake, type, advance }
}

describe('PeopleSearchPage', () => {
  it('searches after 300 ms and only from 2 characters', async () => {
    const { fake, type, advance } = setup()
    type('g')
    await advance(1000)
    expect(fake.calls).not.toHaveBeenCalled()
    expect(screen.getByText(he.people.minChars)).toBeInTheDocument()

    type('ga')
    await advance(299)
    expect(fake.calls).not.toHaveBeenCalled()
    await advance(1)
    expect(fake.log()).toEqual(['GET /users/search?q=ga'])
    await vi.waitFor(() => expect(screen.getByText('Dana')).toBeInTheDocument())
    expect(screen.getByText('@dana')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: `${he.follow.follow} Dana` })).toBeInTheDocument()
  })

  it('waits for a pause in typing and searches once', async () => {
    const { fake, type, advance } = setup()
    type('g')
    await advance(200)
    type('ga')
    await advance(200)
    type('gal')
    await advance(300)
    expect(fake.log()).toEqual(['GET /users/search?q=gal'])
  })

  it('trims the query and ignores whitespace-only input', async () => {
    const { fake, type, advance } = setup()
    type('   ')
    await advance(500)
    expect(fake.calls).not.toHaveBeenCalled()
    type('ga ')
    await advance(300)
    expect(fake.log()).toEqual(['GET /users/search?q=ga'])
  })

  it('shows an empty state when nobody matches', async () => {
    const { type, advance } = setup([])
    type('ga')
    await advance(300)
    await vi.waitFor(() => expect(screen.getByText(he.people.empty)).toBeInTheDocument())
  })

  it('does not offer a follow button for yourself', async () => {
    const { type, advance } = setup([{ ...DANA, follow_state: 'self' }])
    type('ga')
    await advance(300)
    await vi.waitFor(() => expect(screen.getByText('Dana')).toBeInTheDocument())
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows an error when the search fails', async () => {
    const fake = fakeApi({})
    renderApp(<PeopleSearchPage />, { api: fake.api })
    fireEvent.change(screen.getByRole('searchbox', { name: he.people.search }), {
      target: { value: 'ga' },
    })
    await act(() => vi.advanceTimersByTimeAsync(300))
    await vi.waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(he.common.error))
  })
})
