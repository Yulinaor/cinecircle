import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { WishlistItem, WishlistStatus } from '../api/types'
import { LangLabel } from '../i18n/LangLabel'
import { useActionName } from '../people/actionName'
import { TasteChip } from '../taste/TasteLine'
import { useWishlistMutations } from './useWishlistMutations'

const SECONDARY =
  'inline-flex min-h-11 items-center justify-center gap-1 rounded-xl border border-line bg-surface px-4 text-sm font-semibold text-ink hover:bg-bg disabled:opacity-60'
const PRIMARY =
  'inline-flex min-h-11 items-center justify-center rounded-xl bg-accent px-4 text-sm font-semibold text-white disabled:opacity-60'

/**
 * One saved title: poster, name, where it came from, and the actions for its tab. Each action is
 * named "<action> <title>", so identical buttons in a list can be told apart.
 */
export function WishlistRow({ item }: { item: WishlistItem }) {
  const { t } = useTranslation()
  const { setStatus, remove } = useWishlistMutations()
  const nameId = useId()
  const { title, via, my_post, taste } = item
  const busy = setStatus.isPending || remove.isPending
  const failed = setStatus.isError || remove.isError
  const primaryName = useActionName(nameId)
  const moveName = useActionName(nameId)
  const removeName = useActionName(nameId)
  const rateName = useActionName(nameId)

  const move = (status: WishlistStatus) => {
    remove.reset()
    setStatus.mutate({ titleId: title.id, status })
  }
  const drop = () => {
    setStatus.reset()
    remove.mutate(title.id)
  }

  return (
    <li className="flex gap-3 rounded-2xl border border-line bg-surface p-3">
      {title.poster_url ? (
        <img
          src={title.poster_url}
          alt=""
          loading="lazy"
          className="aspect-[2/3] w-16 shrink-0 self-start rounded-xl bg-line object-cover"
        />
      ) : (
        <div
          aria-hidden="true"
          data-testid="poster-placeholder"
          className="aspect-[2/3] w-16 shrink-0 self-start rounded-xl bg-line"
        />
      )}
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <h2 className="text-lg font-bold leading-snug text-ink">
          <Link
            id={nameId}
            to={`/titles/${title.id}`}
            dir="auto"
            className="inline-flex min-h-11 items-center hover:underline"
          >
            {title.name}
          </Link>
        </h2>
        <LangLabel lang={title.name_lang} />
        {taste && (
          <p>
            <TasteChip fit={taste.fit} />
          </p>
        )}
        <p className="text-sm text-muted">
          {title.year_start !== null && (
            <>
              <bdi>{title.year_start}</bdi>
              {' · '}
            </>
          )}
          {t(title.media_type === 'movie' ? 'compose.movie' : 'compose.series')}
        </p>
        <p className="text-sm text-muted">
          {via ? (
            <Link
              to={`/posts/${via.post_id}`}
              dir="auto"
              className="inline-flex min-h-11 items-center font-medium text-accent hover:underline"
            >
              {t('wishlist.via', { name: via.author.display_name })}
            </Link>
          ) : (
            t(`wishlist.from.${item.source}`)
          )}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          {item.status === 'want' ? (
            <button
              type="button"
              {...primaryName}
              disabled={busy}
              onClick={() => move('watched')}
              className={PRIMARY}
            >
              {t('wishlist.markWatched')}
            </button>
          ) : (
            <>
              {my_post ? (
                <Link to={`/posts/${my_post.id}`} {...rateName} className={SECONDARY}>
                  {t('wishlist.yourRating')}{' '}
                  {/* One left-to-right run, so a right-to-left screen still reads "9.0". */}
                  <bdi dir="ltr" className="font-extrabold">
                    {my_post.rating.toFixed(1)}
                  </bdi>
                </Link>
              ) : (
                <Link to={`/post?title=${title.id}`} {...rateName} className={PRIMARY}>
                  {t('wishlist.rateNow')}
                </Link>
              )}
              <button
                type="button"
                {...moveName}
                disabled={busy}
                onClick={() => move('want')}
                className={SECONDARY}
              >
                {t('wishlist.backToWant')}
              </button>
            </>
          )}
          <button
            type="button"
            {...removeName}
            disabled={busy}
            onClick={drop}
            className={SECONDARY}
          >
            {t('wishlist.remove')}
          </button>
        </div>
        {failed && (
          <p role="alert" className="text-xs font-medium text-danger">
            {t('common.error')}
          </p>
        )}
      </div>
    </li>
  )
}
