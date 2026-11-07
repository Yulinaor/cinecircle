import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router'
import { ApiError } from '../api/client'
import type { PostCard } from '../api/types'
import { PostForm, type PostFormValues } from '../compose/PostForm'
import { usePostMutations, type PostChanges } from '../compose/usePostMutations'
import { NotFoundPage } from '../pages/NotFoundPage'
import { useSeasonName } from './seasonName'
import { parsePostId, usePost } from './usePost'

const SECONDARY =
  'min-h-11 rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line'

/** `/posts/:id/edit`. Only the author gets the editor; everyone else, and a missing post, gets Not found. */
export function EditPostPage() {
  const postId = parsePostId(useParams().id)
  return postId === null ? <NotFoundPage /> : <EditPostBody id={postId} />
}

function EditPostBody({ id }: { id: number }) {
  const { t } = useTranslation()
  const post = usePost(id)
  if (post.error instanceof ApiError && post.error.status === 404) return <NotFoundPage />
  if (post.data && post.data.author.follow_state !== 'self') return <NotFoundPage />
  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-6">
      {post.isError ? (
        <div role="alert" className="flex flex-col items-start gap-3">
          <p className="text-sm font-medium text-danger">{t('common.error')}</p>
          <button type="button" onClick={() => void post.refetch()} className={SECONDARY}>
            {t('common.retry')}
          </button>
        </div>
      ) : !post.data ? (
        <p role="status" className="text-muted">
          {t('auth.loading')}
        </p>
      ) : (
        <EditPostForm post={post.data} />
      )}
    </section>
  )
}

/** Only the fields that differ from the post as loaded. */
function changesFrom(post: PostCard, values: PostFormValues): PostChanges {
  const changes: PostChanges = {}
  if (values.rating !== post.rating) changes.rating = values.rating
  if (values.opinion !== post.opinion) changes.opinion = values.opinion
  if (values.contains_spoilers !== post.contains_spoilers) {
    changes.contains_spoilers = values.contains_spoilers
  }
  if (values.is_shared !== post.is_shared) changes.is_shared = values.is_shared
  return changes
}

function EditPostForm({ post }: { post: PostCard }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { update, remove } = usePostMutations()
  const [confirming, setConfirming] = useState(false)
  const seasonName = useSeasonName()
  const { title, season } = post
  const seasonLabel = season
    ? seasonName(season.number, season.name, season.name_lang)
    : title.media_type === 'series'
      ? t('post.wholeSeries')
      : null

  function submit(values: PostFormValues) {
    const changes = changesFrom(post, values)
    if (Object.keys(changes).length === 0) {
      void navigate(`/posts/${post.id}`)
      return
    }
    update.mutate({ id: post.id, changes }, { onSuccess: () => void navigate(`/posts/${post.id}`) })
  }

  return (
    <>
      <header className="flex flex-col gap-1">
        <h1 className="text-lg font-bold leading-snug text-ink">
          <Link to={`/titles/${title.id}`} dir="auto" className="hover:underline">
            {title.name}
          </Link>
        </h1>
        {seasonLabel && (
          <p dir="auto" className="text-sm font-medium text-muted">
            {seasonLabel}
          </p>
        )}
      </header>
      <PostForm
        initial={{
          rating: post.rating,
          opinion: post.opinion,
          contains_spoilers: post.contains_spoilers,
          is_shared: post.is_shared,
        }}
        onSubmit={submit}
        submitLabel={t('compose.save')}
        busy={update.isPending}
        error={update.isError ? t('common.error') : null}
      />
      {confirming ? (
        <div
          role="group"
          aria-labelledby="confirm-delete"
          className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4"
        >
          <p id="confirm-delete" className="font-medium text-ink">
            {t('compose.confirmDelete')}
          </p>
          {remove.isError && (
            <p role="alert" className="text-sm font-medium text-danger">
              {t('common.error')}
            </p>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              disabled={remove.isPending}
              onClick={() => remove.mutate(post.id, { onSuccess: () => void navigate('/profile') })}
              className="min-h-11 rounded-xl bg-danger px-4 font-semibold text-white disabled:opacity-60"
            >
              {t('compose.yes')}
            </button>
            <button
              type="button"
              disabled={remove.isPending}
              onClick={() => {
                remove.reset()
                setConfirming(false)
              }}
              className={SECONDARY}
            >
              {t('compose.cancel')}
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="min-h-11 rounded-xl border border-danger bg-surface px-4 font-semibold text-danger hover:bg-line"
        >
          {t('compose.delete')}
        </button>
      )}
    </>
  )
}
