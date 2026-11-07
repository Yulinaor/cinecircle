import { Fragment, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { Taste } from '../api/types'

type Isolated = { text: string; dir: 'auto' | 'ltr' }

/**
 * Translates `key` with some values wrapped in `<bdi>`, wherever the language puts them: each is
 * interpolated as a private-use marker (`name`), then the result is split at the
 * markers. Plain strings in `plain` are interpolated as they are.
 */
function useIsolating() {
  const { t } = useTranslation()
  return (key: string, isolated: Record<string, Isolated>, plain: Record<string, string> = {}) => {
    const marks = Object.fromEntries(Object.keys(isolated).map((k) => [k, `${k}`]))
    const parts = t(key, { ...plain, ...marks }).split(/(\w+)/)
    // split() with a capture group alternates: text, name, text, name, ...
    return parts.map((part, i) => {
      if (i % 2 === 0) {
        // A "%" right after an isolated number belongs to it (see below).
        const afterNumber = i > 0 && isolated[parts[i - 1]!]?.dir === 'ltr'
        return afterNumber && part.startsWith('%') ? part.slice(1) : part
      }
      const value = isolated[part]
      if (!value) return null
      // Keep the "%" inside the isolate, or a right-to-left line shows it as "%76".
      const percent = value.dir === 'ltr' && (parts[i + 1] ?? '').startsWith('%')
      return (
        <bdi key={i} dir={value.dir}>
          {value.text}
          {percent && '%'}
        </bdi>
      )
    })
  }
}

const number = (n: number): Isolated => ({ text: String(n), dir: 'ltr' })

/** "76% match" with the number isolated; the pill form is for lists, `bare` for inside a line. */
export function TasteChip({ fit, bare = false }: { fit: number; bare?: boolean }) {
  const isolating = useIsolating()
  const text = isolating('taste.match', { pct: number(fit) })
  if (bare) return <span className="font-bold">{text}</span>
  return (
    <span
      data-testid="taste-chip"
      className="inline-flex min-h-6 items-center rounded-full bg-accent-soft px-2 text-xs font-bold text-accent"
    >
      {text}
    </span>
  )
}

/**
 * One line: the match chip, then why — the genres that fit the viewer, how often they agree with
 * the post's author (only with `authorName`), or "Based on your ratings" when there is neither.
 */
export function TasteLine({ taste, authorName }: { taste: Taste; authorName?: string }) {
  const { t, i18n } = useTranslation()
  const isolating = useIsolating()

  const parts: ReactNode[] = []
  const [first, second] = taste.genres
  if (first !== undefined && second !== undefined) {
    // English names are title-cased ("Action & Adventure"); the second reads mid-sentence.
    const b = i18n.language === 'en' ? second.toLocaleLowerCase('en') : second
    parts.push(t('taste.genres_two', { a: first, b }))
  } else if (first !== undefined) {
    parts.push(t('taste.genres_one', { a: first }))
  }
  if (taste.agreement !== null && authorName !== undefined) {
    parts.push(
      isolating('taste.agree', {
        pct: number(taste.agreement),
        name: { text: authorName, dir: 'auto' },
      }),
    )
  }
  if (parts.length === 0) parts.push(t('taste.basedOnYou'))

  return (
    <p data-testid="taste-line" className="text-sm font-medium text-accent">
      <TasteChip fit={taste.fit} bare />
      {parts.map((part, i) => (
        <Fragment key={i}>
          {' · '}
          {part}
        </Fragment>
      ))}
    </p>
  )
}
