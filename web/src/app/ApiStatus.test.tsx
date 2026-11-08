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
  const banner = screen.getByText('מעיר את השרת…')
  expect(banner).not.toHaveClass('sr-only')
  expect(banner).toHaveClass('fixed', 'inset-x-4')
  // The banner is inside the one live region, so it is announced once, not twice.
  expect(screen.getByRole('status')).toContainElement(banner)
  expect(screen.getAllByText('מעיר את השרת…')).toHaveLength(1)
})

it('keeps one status node as the state changes, so the waking text is announced', () => {
  state.status = 'checking'
  const { rerender } = render(<ApiStatus />)
  const node = screen.getByRole('status')
  expect(node).not.toHaveTextContent('מעיר את השרת…')
  state.status = 'waking'
  rerender(<ApiStatus />)
  expect(screen.getByRole('status')).toBe(node)
  expect(node).toHaveTextContent('מעיר את השרת…')
  state.status = 'connected'
  rerender(<ApiStatus />)
  expect(screen.getByRole('status')).toBe(node)
  expect(screen.getByText('מחובר')).toHaveClass('sr-only')
})

it('shows no banner once connected, only the dot with its text for screen readers', () => {
  state.status = 'connected'
  render(<ApiStatus />)
  expect(screen.getByRole('status')).toBeInTheDocument()
  expect(screen.getByText('מחובר')).toHaveClass('sr-only')
  expect(document.querySelector('.fixed')).toBeNull()
})
