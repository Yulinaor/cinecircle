import { useTranslation } from 'react-i18next'

export type Isolated = { text: string; dir: 'auto' | 'ltr' }

/**
 * Translates `key` with some values wrapped in `<bdi>`, wherever the language puts them: each is
 * interpolated as a private-use marker (`name`), then the result is split at the
 * markers. Plain strings in `plain` are interpolated as they are. `plural` picks the `_one` /
 * `_other` form of `key`; `{{count}}` itself is still taken from `isolated` or `plain`.
 */
export function useIsolating() {
  const { t } = useTranslation()
  return (
    key: string,
    isolated: Record<string, Isolated>,
    plain: Record<string, string> = {},
    plural?: number,
  ) => {
    const marks = Object.fromEntries(Object.keys(isolated).map((k) => [k, `${k}`]))
    const values = { ...plain, ...marks }
    // i18next reads `count` to pick the plural form and would also interpolate it, so with
    // `plural` the values go in `replace`, which takes over interpolation.
    const text = plural === undefined ? t(key, values) : t(key, { count: plural, replace: values })
    const parts = text.split(/(\w+)/)
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

export const number = (n: number): Isolated => ({
  text: String(n),
  dir: 'ltr',
})
