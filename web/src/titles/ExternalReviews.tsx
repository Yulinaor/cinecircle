import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { ExternalReview, ReviewsPage } from '../api/types'
import { useApi } from '../api/useApi'
import { number, useIsolating } from '../taste/useIsolating'

/**
 * What people wrote about the title on TMDB. Reviews are an optional extra: nothing shows while they
 * load, if they fail or when there are none. Each card is plainly someone else's (R4.2): bordered
 * and attributed, with no CineCircle avatar and no follow control.
 */
export function ExternalReviews({ titleId }: { titleId: number }) {
  const { t } = useTranslation()
  const api = useApi()
  const query = useQuery({
    queryKey: ['title', titleId, 'reviews'],
    queryFn: ({ signal }) => api<ReviewsPage>(`/titles/${titleId}/reviews`, { signal }),
  })
  const reviews = query.data?.reviews ?? []
  if (reviews.length === 0) return null
  return (
    <section aria-labelledby="title-reviews" className="flex flex-col gap-3">
      <h2 id="title-reviews" className="text-lg font-bold text-ink">
        {t('reviews.heading')}
      </h2>
      {reviews.map((review) => (
        <ReviewCard key={review.url} review={review} />
      ))}
    </section>
  )
}

function ReviewCard({ review }: { review: ExternalReview }) {
  const { t } = useTranslation()
  const isolate = useIsolating()
  return (
    <article className="flex min-w-0 flex-col gap-2 rounded-xl border border-dashed border-line bg-bg p-3">
      <p className="text-sm text-muted">
        {isolate('reviews.by', { author: { text: review.author_name, dir: 'auto' } })}
        {review.author_rating !== null && (
          <>
            {' · '}
            {isolate('reviews.rated', { rating: number(review.author_rating) })}
          </>
        )}
      </p>
      <p dir="auto" className="whitespace-pre-wrap break-words text-ink">
        {review.excerpt}
      </p>
      <a
        href={review.url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex min-h-11 items-center self-start text-sm font-medium text-accent underline"
      >
        {t('reviews.read')}
      </a>
    </article>
  )
}
