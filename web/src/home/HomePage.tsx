import { useInfiniteQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { PostPage } from '../api/types'
import { useApi } from '../api/useApi'
import { useLang } from '../i18n/useLang'
import { postKeys } from '../posts/keys'
import { PostList } from '../posts/PostList'

const FILTERS = ['all', 'movie', 'series'] as const
type FeedType = (typeof FILTERS)[number]

const LINK =
  'inline-flex min-h-11 items-center justify-center rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line'

/** `/`: the shared posts of the people you follow (and your own), newest first. */
export function HomePage() {
  const { t } = useTranslation()
  const api = useApi()
  const lang = useLang()
  const [type, setType] = useState<FeedType>('all')

  const feed = useInfiniteQuery({
    queryKey: postKeys.feed(type, lang),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api<PostPage>(
        `/feed?type=${type}&lang=${lang}${pageParam === null ? '' : `&cursor=${encodeURIComponent(pageParam)}`}`,
        { signal },
      ),
    getNextPageParam: (page) => page.next_cursor,
  })

  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-6">
      <h1 className="text-2xl font-extrabold">{t('nav.home')}</h1>
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={type === value}
            onClick={() => setType(value)}
            className={`min-h-11 rounded-full border px-4 font-medium ${
              type === value
                ? 'border-accent bg-accent-soft text-accent'
                : 'border-line bg-surface text-ink hover:bg-line'
            }`}
          >
            {t(`feed.filter.${value}`)}
          </button>
        ))}
      </div>
      <PostList
        query={feed}
        empty={
          <div className="flex flex-col items-start gap-3">
            <p className="text-muted">{t('feed.empty')}</p>
            <div className="flex flex-wrap gap-2">
              <Link to="/people" className={LINK}>
                {t('feed.findPeople')}
              </Link>
              <Link to="/post" className={LINK}>
                {t('feed.createPost')}
              </Link>
            </div>
          </div>
        }
      />
    </section>
  )
}
