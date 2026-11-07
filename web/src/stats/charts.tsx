import type { ReactNode } from 'react'

/** `value` as a share of `max`, as a CSS percentage; 0% when there is nothing to compare against. */
function share(value: number, max: number): string {
  if (!(max > 0) || !(value > 0)) return '0%'
  return `${Math.round(Math.min(1, value / max) * 10000) / 100}%`
}

export type Column = { key: string; label: string; value: number }

/**
 * Vertical columns side by side, in reading direction (in Hebrew the first column is at the right).
 * The value sits in a `<bdi>` above each column and the label below; the bars themselves are
 * decoration, so every column reads out as "label: value". `labelledBy` is the id of the heading.
 */
export function ColumnChart({ items, labelledBy }: { items: Column[]; labelledBy: string }) {
  const max = Math.max(0, ...items.map((item) => item.value))
  return (
    <ul role="list" aria-labelledby={labelledBy} className="flex h-44 items-stretch gap-1">
      {items.map((item) => (
        <li
          key={item.key}
          role="listitem"
          aria-label={`${item.label}: ${item.value}`}
          className="flex min-w-0 flex-1 flex-col items-center gap-1"
        >
          <bdi dir="ltr" className="text-xs font-bold text-ink">
            {item.value}
          </bdi>
          <div className="flex w-full flex-1 items-end justify-center">
            <div
              data-testid="bar"
              aria-hidden="true"
              className="w-3/4 max-w-8 rounded-t-md bg-accent"
              style={{ blockSize: share(item.value, max) }}
            />
          </div>
          <span className="flex min-h-8 items-start text-center text-xs leading-tight text-muted">
            {item.label}
          </span>
        </li>
      ))}
    </ul>
  )
}

export type Bar = {
  key: string
  label: ReactNode
  detail: ReactNode
  value: number
  max: number
}

/**
 * One row per item: the label with its detail line, and under them a track whose bar fills
 * `value / max` from the start edge (the right in Hebrew). `labelledBy` is the id of the heading.
 */
export function BarList({ items, labelledBy }: { items: Bar[]; labelledBy: string }) {
  return (
    <ul role="list" aria-labelledby={labelledBy} className="flex flex-col gap-3">
      {items.map((item) => (
        <li key={item.key} className="flex flex-col gap-1">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3">
            <span className="min-w-0 break-words font-medium text-ink">{item.label}</span>
            <span className="text-sm text-muted">{item.detail}</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-line">
            <div
              data-testid="bar"
              aria-hidden="true"
              className="h-full rounded-full bg-accent"
              style={{ inlineSize: share(item.value, item.max) }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}
