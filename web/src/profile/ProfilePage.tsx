import { useInfiniteQuery } from '@tanstack/react-query'
import { useId, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useParams } from 'react-router'
import { ApiError } from '../api/client'
import type { PostPage, UserProfile } from '../api/types'
import { useApi } from '../api/useApi'
import { useLang } from '../i18n/useLang'
import { useMe } from '../me/useMe'
import { NotFoundPage } from '../pages/NotFoundPage'
import { Avatar } from '../people/Avatar'
import { FollowButton } from '../people/FollowButton'
import { postKeys } from '../posts/keys'
import { PostList } from '../posts/PostList'
import { useProfile } from './useProfile'

const SECTION = 'mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-6'
const LINK =
  'inline-flex min-h-11 items-center justify-center rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line'
const BUTTON =
  'min-h-11 rounded-xl border border-line bg-surface px-4 font-medium text-ink hover:bg-line'

function Loading() {
  const { t } = useTranslation()
  return (
    <section className={SECTION}>
      <p role="status" className="text-muted">
        {t('auth.loading')}
      </p>
    </section>
  )
}

/** `/profile`: your own profile. */
export function OwnProfilePage() {
  const { t } = useTranslation()
  const me = useMe()
  const username = me.data?.profile?.username
  if (username) return <ProfilePage username={username} />
  if (!me.isError) return <Loading />
  return (
    <section className={SECTION}>
      <p role="alert" className="text-sm font-medium text-danger">
        {t('common.error')}
      </p>
    </section>
  )
}

/** `/u/:username`: anyone's profile; your own username goes to `/profile`. */
export function UserProfilePage() {
  const me = useMe()
  const username = (useParams().username ?? '').toLowerCase()
  if (!me.data && !me.isError) return <Loading />
  if (me.data?.profile?.username === username) return <Navigate to="/profile" replace />
  return <ProfilePage username={username} />
}

/**
 * A profile in whichever state the API allows: the owner (counts and account links), an approved
 * follower (bio, post count, posts) or locked (name, avatar, @username and the follow control, and
 * not a single request for posts). A missing user is Not found.
 */
export function ProfilePage({ username }: { username: string }) {
  const { t } = useTranslation()
  const profile = useProfile(username)
  const nameId = useId()

  if (profile.error instanceof ApiError && profile.error.status === 404) return <NotFoundPage />
  if (profile.isError) {
    return (
      <section className={SECTION}>
        <div role="alert" className="flex flex-col items-start gap-3">
          <p className="text-sm font-medium text-danger">{t('common.error')}</p>
          <button type="button" onClick={() => void profile.refetch()} className={BUTTON}>
            {t('common.retry')}
          </button>
        </div>
      </section>
    )
  }
  if (!profile.data) return <Loading />

  const user = profile.data
  const { details } = user
  return (
    <section className={SECTION}>
      <header className="flex items-center gap-3">
        <Avatar url={user.avatar_url} name={user.display_name} />
        <div className="min-w-0 flex-1">
          <h1 id={nameId} dir="auto" className="break-words text-2xl font-extrabold">
            {user.display_name}
          </h1>
          <p className="truncate text-sm text-muted">
            <bdi>@{user.username}</bdi>
          </p>
        </div>
        <FollowButton username={user.username} state={user.follow_state} nameId={nameId} />
      </header>

      {details === null ? (
        <p className="text-muted">{t('profile.locked')}</p>
      ) : (
        <>
          {details.bio && (
            <p dir="auto" className="whitespace-pre-line break-words text-ink">
              {details.bio}
            </p>
          )}
          <Stats details={details} />
          {user.follow_state === 'self' && (
            <div className="flex flex-wrap gap-2">
              <Link to="/settings" className={LINK}>
                {t('profile.editProfile')}
              </Link>
              <Link to="/connections" className={LINK}>
                {t('profile.connections')}
              </Link>
              <Link to="/people" className={LINK}>
                {t('profile.findPeople')}
              </Link>
            </div>
          )}
          <ProfilePosts username={user.username} />
        </>
      )}
    </section>
  )
}

/** Posts always; followers and following only for the owner (the API sends null to everyone else). */
function Stats({ details }: { details: NonNullable<UserProfile['details']> }) {
  const { t } = useTranslation()
  const stat = (count: number, label: string, to?: string): ReactNode => {
    const content = (
      <>
        <bdi className="font-bold text-ink">{count}</bdi> <span className="text-muted">{label}</span>
      </>
    )
    return (
      <li>
        {to ? (
          <Link to={to} className="inline-flex min-h-11 items-center hover:underline">
            {content}
          </Link>
        ) : (
          content
        )}
      </li>
    )
  }
  return (
    <ul className="flex flex-wrap items-center gap-x-5">
      {stat(details.post_count, t('profile.posts', { count: details.post_count }))}
      {details.followers_count !== null &&
        stat(
          details.followers_count,
          t('profile.followers', { count: details.followers_count }),
          '/connections',
        )}
      {details.following_count !== null &&
        stat(
          details.following_count,
          t('profile.following', { count: details.following_count }),
          '/connections',
        )}
    </ul>
  )
}

/** Only mounted once the API has shown the viewer the profile's details, so a locked profile never asks. */
function ProfilePosts({ username }: { username: string }) {
  const { t } = useTranslation()
  const api = useApi()
  const lang = useLang()
  const posts = useInfiniteQuery({
    queryKey: postKeys.user(username, lang),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      api<PostPage>(
        `/users/${encodeURIComponent(username)}/posts?lang=${lang}${
          pageParam === null ? '' : `&cursor=${encodeURIComponent(pageParam)}`
        }`,
        { signal },
      ),
    getNextPageParam: (page) => page.next_cursor,
  })
  return <PostList query={posts} empty={<p className="text-muted">{t('profile.noPosts')}</p>} />
}
