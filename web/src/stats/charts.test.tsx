import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BarList, ColumnChart } from './charts'

const bars = () => screen.getAllByTestId('bar')

describe('ColumnChart', () => {
  it('sizes bars from the data', () => {
    render(
      <>
        <h2 id="t">Chart</h2>
        <ColumnChart
          labelledBy="t"
          items={[
            { key: 'a', label: 'A', value: 3 },
            { key: 'b', label: 'B', value: 4 },
            { key: 'c', label: 'C', value: 0 },
          ]}
        />
      </>,
    )
    expect(bars().map((b) => b.style.blockSize)).toEqual(['75%', '100%', '0%'])
  })

  it('draws zero-height bars, never NaN, when every value is 0', () => {
    const { container } = render(
      <>
        <h2 id="t">Chart</h2>
        <ColumnChart
          labelledBy="t"
          items={[
            { key: 'a', label: 'A', value: 0 },
            { key: 'b', label: 'B', value: 0 },
          ]}
        />
      </>,
    )
    expect(bars().map((b) => b.style.blockSize)).toEqual(['0%', '0%'])
    expect(container.innerHTML).not.toMatch(/NaN|Infinity/)
  })

  it('is a labelled list of "label: value" items with hidden bars', () => {
    render(
      <>
        <h2 id="t">Your ratings</h2>
        <ColumnChart
          labelledBy="t"
          items={[
            { key: '1', label: '1', value: 2 },
            { key: '2', label: '2', value: 5 },
          ]}
        />
      </>,
    )
    const list = screen.getByRole('list', { name: 'Your ratings' })
    const items = within(list).getAllByRole('listitem')
    // Screen readers get one "label: value" text; the visible value and label are hidden from them.
    const spoken = items.map((li) => li.querySelector('.sr-only')?.textContent)
    expect(spoken).toEqual(['1: 2', '2: 5'])
    const value = within(items[1]!).getByText('5')
    expect(value.tagName).toBe('BDI')
    expect(value).toHaveAttribute('aria-hidden', 'true')
    expect(within(items[1]!).getByText('2')).toHaveAttribute('aria-hidden', 'true')
    for (const bar of bars()) expect(bar).toHaveAttribute('aria-hidden', 'true')
  })
})

describe('BarList', () => {
  const items = (max: number) => [
    { key: 'a', label: 'Drama', detail: '3 titles', value: 3, max },
    { key: 'b', label: 'Comedy', detail: '1 title', value: 1, max },
  ]

  it('sizes bars from the data', () => {
    render(
      <>
        <h2 id="t">Genres</h2>
        <BarList labelledBy="t" items={items(4)} />
      </>,
    )
    expect(bars().map((b) => b.style.inlineSize)).toEqual(['75%', '25%'])
    expect(screen.getByRole('list', { name: 'Genres' })).toBeInTheDocument()
    expect(screen.getByText('Drama')).toBeInTheDocument()
    expect(screen.getByText('3 titles')).toBeInTheDocument()
    for (const bar of bars()) expect(bar).toHaveAttribute('aria-hidden', 'true')
  })

  it('draws zero-width bars, never NaN, when max is 0', () => {
    const { container } = render(
      <>
        <h2 id="t">Genres</h2>
        <BarList labelledBy="t" items={items(0)} />
      </>,
    )
    expect(bars().map((b) => b.style.inlineSize)).toEqual(['0%', '0%'])
    expect(container.innerHTML).not.toMatch(/NaN|Infinity/)
  })
})
