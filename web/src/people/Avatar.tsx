import { useState } from 'react'

const segmenter = typeof Intl.Segmenter === 'function' ? new Intl.Segmenter() : null

/** First user-perceived character (a Hebrew letter, an emoji, a letter with accents), upper-cased. */
function initialOf(name: string): string {
  const trimmed = name.trim()
  if (!trimmed) return '?'
  const first = segmenter
    ? ([...segmenter.segment(trimmed)][0]?.segment ?? '')
    : (Array.from(trimmed)[0] ?? '')
  return first.toLocaleUpperCase() || '?'
}

/**
 * Profile picture, or the name's first letter on a token colour. Decorative: the name is always
 * shown next to it, so the image has an empty alt.
 */
export function Avatar({ url, name }: { url: string | null; name: string }) {
  const [failed, setFailed] = useState<string | null>(null)
  const className = 'size-10 shrink-0 rounded-full'
  if (url && failed !== url) {
    return (
      <img
        src={url}
        alt=""
        onError={() => setFailed(url)}
        className={`${className} bg-line object-cover`}
      />
    )
  }
  return (
    <span
      aria-hidden="true"
      className={`${className} flex items-center justify-center bg-accent-soft text-base font-bold text-accent`}
    >
      {initialOf(name)}
    </span>
  )
}
