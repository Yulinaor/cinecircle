import { render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { initI18n, setLocale } from '../i18n'
import { ApiStatus } from './ApiStatus'

const state = vi.hoisted(() => ({ status: 'waking' }))
vi.mock('../api/useApiStatus', () => ({ useApiStatus: () => state.status }))

beforeEach(async () => {
  state.status = 'waking'
  initI18n()
  await setLocale('he')
})

it('renders the waking message in Hebrew inside role=status', () => {
  render(<ApiStatus />)
  expect(screen.getByRole('status')).toHaveTextContent('מעיר את השרת…')
})

it('shows a visible banner while the server is waking', () => {
  render(<ApiStatus />)
  const banner = screen.getByRole('status')
  expect(banner).toHaveTextContent('מעיר את השרת…')
  expect(banner).not.toHaveClass('sr-only')
  expect(banner).toHaveClass('fixed', 'inset-x-4')
  // Only one live region says it: the dot beside the header controls is decoration then.
  expect(screen.getAllByText('מעיר את השרת…')).toHaveLength(1)
})

it('shows no banner once connected, only the dot with its text for screen readers', () => {
  state.status = 'connected'
  render(<ApiStatus />)
  const status = screen.getByRole('status')
  expect(status).not.toHaveClass('fixed')
  expect(screen.getByText('מחובר')).toHaveClass('sr-only')
})
