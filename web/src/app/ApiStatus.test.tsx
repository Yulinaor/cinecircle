import { render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { initI18n, setLocale } from '../i18n'
import { ApiStatus } from './ApiStatus'

vi.mock('../api/useApiStatus', () => ({ useApiStatus: () => 'waking' }))

beforeEach(async () => {
  initI18n()
  await setLocale('he')
})

it('renders the waking message in Hebrew inside role=status', () => {
  render(<ApiStatus />)
  expect(screen.getByRole('status')).toHaveTextContent('מעיר את השרת…')
})

it('shows only the dot on phones: the text is still there for screen readers', () => {
  render(<ApiStatus />)
  expect(screen.getByText('מעיר את השרת…')).toHaveClass('sr-only')
})
