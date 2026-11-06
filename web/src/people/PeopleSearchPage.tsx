import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { UserCard } from '../api/types'
import { useApi } from '../api/useApi'
import { UserCardRow } from './UserCardRow'

export const SEARCH_DEBOUNCE_MS = 300
export const SEARCH_MIN_CHARS = 2

export function PeopleSearchPage() {
  const { t } = useTranslation()
  const api = useApi()
  const [text, setText] = useState('')
  // The term the API is asked about: the text, trimmed, once typing has paused.
  const [term, setTerm] = useState('')
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  useEffect(() => () => clearTimeout(timer.current), [])

  function onChange(value: string) {
    setText(value)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setTerm(value.trim()), SEARCH_DEBOUNCE_MS)
  }

  const typedEnough = text.trim().length >= SEARCH_MIN_CHARS
  const search = useQuery({
    queryKey: ['people', term],
    enabled: term.length >= SEARCH_MIN_CHARS,
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) =>
      api<{ results: UserCard[] }>(`/users/search?q=${encodeURIComponent(term)}`, { signal }),
  })
  const results = typedEnough ? search.data?.results : undefined

  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-6">
      <h1 className="text-2xl font-extrabold">{t('people.title')}</h1>
      <input
        type="search"
        name="q"
        aria-label={t('people.search')}
        placeholder={t('people.search')}
        autoComplete="off"
        maxLength={50}
        value={text}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-base text-ink placeholder:text-muted"
      />
      {!typedEnough && <p className="text-sm text-muted">{t('people.minChars')}</p>}
      {typedEnough && search.isError && (
        <p role="alert" className="text-sm font-medium text-danger">
          {t('common.error')}
        </p>
      )}
      {typedEnough && !search.isError && !results && (
        <p role="status" className="text-muted">
          {t('auth.loading')}
        </p>
      )}
      {results && results.length === 0 && !search.isPlaceholderData && (
        <p className="text-muted">{t('people.empty')}</p>
      )}
      {results && results.length > 0 && (
        <ul className="flex flex-col gap-2">
          {results.map((user) => (
            <UserCardRow key={user.username} user={user} />
          ))}
        </ul>
      )}
    </section>
  )
}
