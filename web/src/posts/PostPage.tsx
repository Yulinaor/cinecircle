import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router'
import { ApiError } from '../api/client'
import { NotFoundPage } from '../pages/NotFoundPage'
import { PostCard } from './PostCard'
import { usePost } from './usePost'

/** `/posts/:id`. A malformed id, or a post that is missing or hidden from the viewer, is Not found. */
export function PostPage() {
  const { id } = useParams()
  const postId = id !== undefined && /^[1-9]\d*$/.test(id) ? Number(id) : null
  return postId === null || !Number.isSafeInteger(postId) ? (
    <NotFoundPage />
  ) : (
    <PostPageBody id={postId} />
  )
}

function PostPageBody({ id }: { id: number }) {
  const { t } = useTranslation()
  const post = usePost(id)
  if (post.error instanceof ApiError && post.error.status === 404) return <NotFoundPage />
  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-6">
      {post.isError ? (
        <div role="alert" className="flex flex-col items-start gap-3">
          <p className="text-sm font-medium text-danger">{t('common.error')}</p>
          <button
            type="button"
            onClick={() => void post.refetch()}
            className="min-h-11 rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line"
          >
            {t('common.retry')}
          </button>
        </div>
      ) : !post.data ? (
        <p role="status" className="text-muted">
          {t('auth.loading')}
        </p>
      ) : (
        <PostCard post={post.data} />
      )}
    </section>
  )
}
