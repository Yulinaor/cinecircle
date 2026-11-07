import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { TitleSearchItem } from '../api/types'
import { useApi } from '../api/useApi'
import { useLang } from '../i18n/useLang'

export const TITLE_SEARCH_DEBOUNCE_MS = 300

/** Search movies and series (as you type) and pick one. */
export function TitlePicker({ onPick }: { onPick: (item: TitleSearchItem) => void }) {
  const { t } = useTranslation()
  const api = useApi()
  const lang = useLang()
  const [text, setText] = useState('')
  // The term the API is asked about: the text, trimmed, once typing has paused.
  const [term, setTerm] = useState('')
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  useEffect(() => () => clearTimeout(timer.current), [])

  function onChange(value: string) {
    setText(value)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setTerm(value.trim()), TITLE_SEARCH_DEBOUNCE_MS)
  }

  const typed = text.trim() !== ''
  const search = useQuery({
    queryKey: ['titleSearch', term, lang],
    enabled: term !== '',
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) =>
      api<{ results: TitleSearchItem[] }>(
        `/titles/search?q=${encodeURIComponent(term)}&type=all&lang=${lang}`,
        { signal },
      ),
  })
  const results = typed ? search.data?.results : undefined

  return (
    <div className="flex flex-col gap-3">
      <input
        type="search"
        name="q"
        aria-label={t('compose.search')}
        placeholder={t('compose.search')}
        autoComplete="off"
        maxLength={100}
        value={text}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-base text-ink placeholder:text-muted"
      />
      {!typed && <p className="text-sm text-muted">{t('compose.searchHint')}</p>}
      {typed && search.isError && (
        <p role="alert" className="text-sm font-medium text-danger">
          {t('common.error')}
        </p>
      )}
      {typed && !search.isError && !results && (
        <p role="status" className="text-muted">
          {t('auth.loading')}
        </p>
      )}
      {results && results.length === 0 && !search.isPlaceholderData && (
        <p role="status" className="text-sm text-muted">
          {t('compose.noResults')}
        </p>
      )}
      {results && results.length > 0 && (
        <ul className="flex flex-col gap-2">
          {results.map((item) => (
            <li key={`${item.media_type}-${item.tmdb_id}`}>
              <button
                type="button"
                onClick={() => onPick(item)}
                className="flex min-h-11 w-full items-center gap-3 rounded-2xl border border-line bg-surface p-2 text-start hover:bg-bg"
              >
                {item.poster_url ? (
                  <img
                    src={item.poster_url}
                    alt=""
                    loading="lazy"
                    className="aspect-[2/3] w-10 shrink-0 rounded-lg bg-line object-cover"
                  />
                ) : (
                  <span
                    aria-hidden="true"
                    className="aspect-[2/3] w-10 shrink-0 rounded-lg bg-line"
                  />
                )}
                <span className="flex min-w-0 flex-1 flex-col">
                  <span dir="auto" className="truncate font-semibold text-ink">
                    {item.name}
                  </span>
                  <span className="text-sm text-muted">
                    {item.year !== null && <bdi>{item.year} · </bdi>}
                    {t(item.media_type === 'movie' ? 'compose.movie' : 'compose.series')}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
