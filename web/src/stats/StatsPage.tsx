import { useQuery } from '@tanstack/react-query'
import { useId, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { ImdbBucketKey, MyStats } from '../api/types'
import { useApi } from '../api/useApi'
import { useLang } from '../i18n/useLang'
import { number, useIsolating } from '../taste/useIsolating'
import { BarList, ColumnChart } from './charts'

const BUTTON =
  'min-h-11 rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line'
const LINK =
  'inline-flex min-h-11 items-center justify-center rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line'

/** A gap under this (in rating points) reads as "like IMDb". */
const SAME_BELOW = 0.05

const oneDecimal = (n: number) => ({ text: n.toFixed(1), dir: 'ltr' as const })

/** A titled chart: the heading names the region and labels the list inside it. */
function ChartSection({
  title,
  children,
}: {
  title: string
  children: (headingId: string) => ReactNode
}) {
  const id = useId()
  return (
    <section aria-labelledby={id} className="flex min-w-0 flex-col gap-3">
      <h2 id={id} className="text-lg font-bold">
        {title}
      </h2>
      {children(id)}
    </section>
  )
}

function ImdbSection({ imdb }: { imdb: MyStats['imdb'] }) {
  const { t } = useTranslation()
  const isolating = useIsolating()
  const gap = imdb.mean_gap
  const wording: 'higher' | 'lower' | 'same' | null =
    gap === null ? null : Math.abs(gap) < SAME_BELOW ? 'same' : gap > 0 ? 'higher' : 'lower'
  return (
    <ChartSection title={t('stats.imdb.title')}>
      {(headingId) =>
        imdb.compared === 0 ? (
          <p className="text-muted">{t('stats.imdb.empty')}</p>
        ) : (
          <>
            {gap !== null && wording !== null && (
              <p className="font-medium text-ink">
                {wording === 'same'
                  ? t('stats.imdb.same')
                  : isolating(`stats.imdb.${wording}`, { gap: oneDecimal(Math.abs(gap)) })}
              </p>
            )}
            <ColumnChart
              labelledBy={headingId}
              items={imdb.buckets.map((bucket) => ({
                key: bucket.key,
                label: t(`stats.imdb.bucket.${bucket.key satisfies ImdbBucketKey}`),
                value: bucket.count,
              }))}
            />
            <p className="text-sm text-muted">
              {isolating('stats.imdb.compared', { count: number(imdb.compared) }, {}, imdb.compared)}
            </p>
          </>
        )
      }
    </ChartSection>
  )
}

/** `/stats`: your own numbers, drawn as four charts. Nobody else can see them. */
export function StatsPage() {
  const { t } = useTranslation()
  const api = useApi()
  const lang = useLang()
  const isolating = useIsolating()
  const stats = useQuery({
    queryKey: ['stats', lang],
    queryFn: ({ signal }) => api<MyStats>(`/me/stats?lang=${lang}`, { signal }),
  })
  const data = stats.data

  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-6 px-4 py-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-extrabold">{t('stats.title')}</h1>
        <p className="text-sm text-muted">{t('stats.privateNote')}</p>
        {data && data.rated > 0 && (
          <p className="font-medium text-ink">
            {isolating('stats.rated', { count: number(data.rated) }, {}, data.rated)}
          </p>
        )}
      </header>

      {!data ? (
        stats.isError ? (
          <div role="alert" className="flex flex-col items-start gap-3">
            <p className="text-sm font-medium text-danger">{t('common.error')}</p>
            <button
              type="button"
              onClick={() => void stats.refetch()}
              disabled={stats.isFetching}
              className={BUTTON}
            >
              {t('common.retry')}
            </button>
          </div>
        ) : (
          <p role="status" className="text-muted">
            {t('auth.loading')}
          </p>
        )
      ) : data.rated === 0 ? (
        <div className="flex flex-col items-start gap-3">
          <p className="text-muted">{t('stats.empty')}</p>
          <Link to="/post" className={LINK}>
            {t('stats.cta')}
          </Link>
        </div>
      ) : (
        <>
          <ChartSection title={t('stats.distribution.title')}>
            {(headingId) => (
              <ColumnChart
                labelledBy={headingId}
                items={data.distribution.map((bucket) => ({
                  key: String(bucket.rating),
                  label: String(bucket.rating),
                  value: bucket.count,
                }))}
              />
            )}
          </ChartSection>

          {data.genres.length > 0 && (
            <ChartSection title={t('stats.genres.title')}>
              {(headingId) => {
                const max = Math.max(...data.genres.map((genre) => genre.count))
                return (
                  <BarList
                    labelledBy={headingId}
                    items={data.genres.map((genre) => ({
                      key: String(genre.id),
                      label: <bdi dir="auto">{genre.name}</bdi>,
                      detail: isolating(
                        'stats.genres.detail',
                        { count: number(genre.count), mean: oneDecimal(genre.mean) },
                        {},
                        genre.count,
                      ),
                      value: genre.count,
                      max,
                    }))}
                  />
                )
              }}
            </ChartSection>
          )}

          <ImdbSection imdb={data.imdb} />

          <ChartSection title={t('stats.agreement.title')}>
            {(headingId) =>
              data.agreement.length === 0 ? (
                <p className="text-muted">{t('stats.agreement.empty')}</p>
              ) : (
                <BarList
                  labelledBy={headingId}
                  items={data.agreement.map((row) => ({
                    key: row.username,
                    label: (
                      <Link
                        to={`/u/${encodeURIComponent(row.username)}`}
                        dir="auto"
                        className="inline-flex min-h-11 items-center hover:underline"
                      >
                        {row.display_name}
                      </Link>
                    ),
                    detail: isolating('stats.agreement.detail', {
                      agreement: number(row.agreement),
                      count: number(row.common),
                    }),
                    value: row.agreement,
                    max: 100,
                  }))}
                />
              )
            }
          </ChartSection>
        </>
      )}
    </section>
  )
}
