import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Avatar } from './Avatar'

describe('Avatar', () => {
  it('shows the first Hebrew letter', () => {
    render(<Avatar url={null} name="  גל בן-ארצי" />)
    expect(screen.getByText('ג')).toBeInTheDocument()
  })

  it('upper-cases a Latin initial', () => {
    render(<Avatar url={null} name="dana" />)
    expect(screen.getByText('D')).toBeInTheDocument()
  })

  it('keeps a whole emoji together', () => {
    render(<Avatar url={null} name="👩🏽‍🎤 Star" />)
    expect(screen.getByText('👩🏽‍🎤')).toBeInTheDocument()
  })

  it('falls back to a question mark for an empty name', () => {
    render(<Avatar url={null} name="  " />)
    expect(screen.getByText('?')).toBeInTheDocument()
  })

  it('shows the picture, and the initial if it fails to load', () => {
    const { container } = render(<Avatar url="https://img.test/a.png" name="Dana" />)
    const img = container.querySelector('img')!
    expect(img).toHaveAttribute('src', 'https://img.test/a.png')
    expect(img).toHaveAttribute('referrerpolicy', 'no-referrer')
    fireEvent.error(img)
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('D')).toBeInTheDocument()
  })
})
