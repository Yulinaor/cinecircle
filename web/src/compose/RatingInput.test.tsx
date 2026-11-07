import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { initI18n, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { RatingInput } from './RatingInput'

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

function Harness({ start = null, spy }: { start?: number | null; spy?: (v: number) => void }) {
  const [value, setValue] = useState<number | null>(start)
  return (
    <RatingInput
      value={value}
      onChange={(v) => {
        spy?.(v)
        setValue(v)
      }}
    />
  )
}

const slider = () => screen.getByRole('slider', { name: he.compose.rating })
const lower = () => screen.getByRole('button', { name: he.compose.decrease })
const raise = () => screen.getByRole('button', { name: he.compose.increase })

describe('RatingInput', () => {
  it('rating starts unset and moves in half steps within 1–10', async () => {
    render(<Harness />)
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(slider()).toHaveAttribute('aria-valuetext', he.compose.ratingUnset)

    // The slider bounds are what a keyboard or pointer can reach.
    expect(slider()).toHaveAttribute('min', '1')
    expect(slider()).toHaveAttribute('max', '10')
    expect(slider()).toHaveAttribute('step', '0.5')

    fireEvent.change(slider(), { target: { value: '1' } })
    await userEvent.click(lower())
    expect(slider()).toHaveAttribute('aria-valuetext', '1.0')

    fireEvent.change(slider(), { target: { value: '10' } })
    await userEvent.click(raise())
    expect(slider()).toHaveAttribute('aria-valuetext', '10.0')

    fireEvent.change(slider(), { target: { value: '8.5' } })
    expect(screen.getByText('8.5')).toBeInTheDocument()
    await userEvent.click(raise())
    expect(slider()).toHaveAttribute('aria-valuetext', '9.0')
    expect(screen.getByText('9.0')).toBeInTheDocument()
    await userEvent.click(lower())
    await userEvent.click(lower())
    expect(slider()).toHaveAttribute('aria-valuetext', '8.0')
  })

  it('starts from the middle when a button is pressed while unset', async () => {
    const spy = vi.fn()
    const { unmount } = render(<Harness spy={spy} />)
    await userEvent.click(raise())
    expect(spy).toHaveBeenLastCalledWith(6)
    unmount()
    render(<Harness spy={spy} />)
    await userEvent.click(lower())
    expect(spy).toHaveBeenLastCalledWith(5)
  })

  it('a tap on the resting position of the unset slider sets that value', () => {
    const spy = vi.fn()
    render(<Harness spy={spy} />)
    // No change event: the native value did not move from 5.5.
    fireEvent.click(slider())
    expect(spy).toHaveBeenCalledExactlyOnceWith(5.5)
    expect(slider()).toHaveAttribute('aria-valuetext', '5.5')
    // Once set, a click alone changes nothing.
    fireEvent.click(slider())
    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('never emits a value outside 1–10 or off the half-step grid', async () => {
    const spy = vi.fn()
    render(<Harness start={9.5} spy={spy} />)
    await userEvent.click(raise())
    await userEvent.click(raise())
    await userEvent.click(raise())
    fireEvent.change(slider(), { target: { value: '0' } })
    fireEvent.change(slider(), { target: { value: '11' } })
    fireEvent.change(slider(), { target: { value: '7.3' } })
    for (const [value] of spy.mock.calls) {
      expect(value).toBeGreaterThanOrEqual(1)
      expect(value).toBeLessThanOrEqual(10)
      expect(Number.isInteger(value * 2)).toBe(true)
    }
  })

  it('is reachable and operable from the keyboard', async () => {
    render(<Harness start={8} />)
    await userEvent.tab()
    expect(lower()).toHaveFocus()
    await userEvent.keyboard('{Enter}')
    expect(slider()).toHaveAttribute('aria-valuetext', '7.5')
    await userEvent.tab()
    await userEvent.tab()
    expect(raise()).toHaveFocus()
    await userEvent.keyboard(' ')
    expect(slider()).toHaveAttribute('aria-valuetext', '8.0')
  })
})
