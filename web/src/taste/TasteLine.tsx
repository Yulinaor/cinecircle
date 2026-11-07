import { Fragment, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { Taste } from '../api/types'
import { number, useIsolating } from './useIsolating'

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
      {/* One child: as direct flex items the bdi and the trailing word would be separate boxes,
          and the space between them would collapse. */}
      <span>{text}</span>
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
