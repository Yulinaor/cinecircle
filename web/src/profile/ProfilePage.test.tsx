import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import type { PostCard, UserProfile } from '../api/types'
import { AppRoutes } from '../app/routes'
import { initI18n, setLocale } from '../i18n'
import he from '../i18n/he.json'
import { UserCardRow } from '../people/UserCardRow'
import { DANA, fakeApi, POST_CARD } from '../test/fakeApi'
import { PROFILE } from '../test/fakeMeApi'
import { renderApp } from '../test/renderApp'

vi.mock('../auth/supabase', () => ({ supabase: null }))

beforeEach(async () => {
  localStorage.clear()
  initI18n()
  await setLocale('he')
})

const ME = { id: 'user-1', email: 'a@b.co', profile: PROFILE }

const GAL = { username: 'gal', display_name: 'Gal', avatar_url: null } as const
const OPINION = 'דעה שרק חברים רואים'

const ownProfile: UserProfile = {
  username: PROFILE.username,
  display_name: PROFILE.display_name,
  avatar_url: null,
  follow_state: 'self',
  details: { bio: 'אוהבת סרטים', post_count: 4, followers_count: 3, following_count: 2 },
}

const privatePost: PostCard = {
  ...POST_CARD,
  id: 8,
  author: { ...ownProfile, follow_state: 'self' },
  opinion: 'דירוג פרטי שלי',
  is_shared: false,
}

const page = (posts: PostCard[]) => ({ posts, next_cursor: null })

function galProfile(over: Partial<UserProfile>): UserProfile {
  return { ...GAL, follow_state: 'none', details: null, ...over }
}

function renderAt(route: string, routes: Record<string, unknown>) {
  const fake = fakeApi({ 'GET /me': ME, ...routes })
  const view = renderApp(<AppRoutes />, { api: fake.api, route })
  return { fake, ...view }
}

describe('ProfilePage', () => {
  it('own profile shows counts, private posts and account links', async () => {
    const { fake } = renderAt('/profile', {
      'GET /users/gal_b': ownProfile,
      'GET /users/gal_b/posts?lang=he': page([privatePost]),
    })
    expect(await screen.findByRole('heading', { name: 'Gal' })).toBeInTheDocument()
    expect(screen.getByText('@gal_b')).toBeInTheDocument()
    expect(screen.getByText('אוהבת סרטים')).toBeInTheDocument()
    expect(screen.getByText(he.profile.posts_other).closest('li')).toHaveTextContent('4')
    expect(screen.getByRole('link', { name: `3 ${he.profile.followers_other}` })).toHaveAttribute(
      'href',
      '/connections',
    )
    expect(screen.getByRole('link', { name: `2 ${he.profile.following_other}` })).toHaveAttribute(
      'href',
      '/connections',
    )
    expect(screen.getByRole('link', { name: he.profile.editProfile })).toHaveAttribute('href', '/settings')
    expect(screen.getByRole('link', { name: he.profile.connections })).toHaveAttribute(
      'href',
      '/connections',
    )
    expect(screen.getByRole('link', { name: he.profile.findPeople })).toHaveAttribute('href', '/people')
    // Own profile has no follow control, and the private post carries its badge.
    expect(screen.queryByRole('button', { name: new RegExp(he.follow.follow) })).toBeNull()
    expect(await screen.findByText('דירוג פרטי שלי')).toBeInTheDocument()
    expect(screen.getByText(he.post.private)).toBeInTheDocument()
    expect(fake.log()).toContain('GET /users/gal_b/posts?lang=he')
  })

  it.each([
    ['he', 1, ['1 פוסט', '1 עוקב/ת', '1 במעקב']],
    ['he', 2, ['2 פוסטים', '2 עוקבים', '2 במעקב']],
    ['en', 1, ['1 Post', '1 Follower', '1 Following']],
    ['en', 2, ['2 Posts', '2 Followers', '2 Following']],
  ] as const)('pluralises counts (%s, %i)', async (lang, n, expected) => {
    const details = { bio: null, post_count: n, followers_count: n, following_count: n }
    const profile = { ...ownProfile, details }
    renderAt('/profile', {
      'GET /me': { ...ME, profile: { ...PROFILE, locale: lang } },
      'GET /users/gal_b': profile,
      [`GET /users/gal_b/posts?lang=${lang}`]: page([]),
    })
    const stats = (await screen.findByRole('link', { name: expected[1] })).closest('ul')!
    expect(within(stats).getAllByRole('listitem').map((li) => li.textContent)).toEqual(expected)
  })

  it('own profile with no posts says so', async () => {
    renderAt('/profile', {
      'GET /users/gal_b': ownProfile,
      'GET /users/gal_b/posts?lang=he': page([]),
    })
    expect(await screen.findByText(he.profile.noPosts)).toBeInTheDocument()
  })

  it('follower sees bio, post count and posts', async () => {
    const { fake } = renderAt('/u/gal', {
      'GET /users/gal': galProfile({
        follow_state: 'following',
        details: { bio: 'ביו של גל', post_count: 5, followers_count: null, following_count: null },
      }),
      'GET /users/gal/posts?lang=he': page([
        { ...POST_CARD, opinion: OPINION, author: { ...GAL, follow_state: 'following' } },
      ]),
    })
    expect(await screen.findByRole('heading', { name: 'Gal' })).toBeInTheDocument()
    expect(screen.getByText('ביו של גל')).toBeInTheDocument()
    expect(screen.getByText(he.profile.posts_other).closest('li')).toHaveTextContent('5')
    expect(screen.getByRole('button', { name: `${he.follow.following} Gal` })).toBeInTheDocument()
    expect(await screen.findByText(OPINION)).toBeInTheDocument()
    // No follower / following counts and no owner links on someone else's profile.
    expect(screen.queryByText(new RegExp(he.profile.followers_other))).toBeNull()
    expect(screen.queryByRole('link', { name: he.profile.editProfile })).toBeNull()
    expect(fake.log()).toContain('GET /users/gal/posts?lang=he')
  })

  it('stranger sees only name, avatar, username and Follow, and no posts request is made', async () => {
    const { fake } = renderAt('/u/gal', { 'GET /users/gal': galProfile({}) })
    expect(await screen.findByRole('heading', { name: 'Gal' })).toBeInTheDocument()
    expect(screen.getByText('@gal')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: `${he.follow.follow} Gal` })).toBeInTheDocument()
    expect(screen.getByText(he.profile.locked)).toBeInTheDocument()
    expect(screen.queryByText(he.profile.noPosts)).toBeNull()
    expect(screen.queryByText(he.profile.posts_other)).toBeNull()
    expect(fake.log()).toEqual(['GET /me', 'GET /users/gal'])
  })

  it('pending requester sees Requested', async () => {
    const { fake } = renderAt('/u/gal', { 'GET /users/gal': galProfile({ follow_state: 'requested' }) })
    expect(await screen.findByRole('button', { name: `${he.follow.requested} Gal` })).toBeInTheDocument()
    expect(screen.getByText(he.profile.locked)).toBeInTheDocument()
    expect(fake.log().filter((k) => k.includes('/posts'))).toEqual([])
  })

  it('unknown user shows Not found', async () => {
    renderAt('/u/nobody', {
      'GET /users/nobody': () => Promise.reject(new ApiError(404, 'not_found')),
    })
    expect(await screen.findByRole('heading', { name: he.notFound.title })).toBeInTheDocument()
  })

  it('offers a retry on other errors', async () => {
    let fail = true
    renderAt('/u/gal', {
      'GET /users/gal': () => {
        if (fail) throw new ApiError(503, 'db_unavailable')
        return galProfile({})
      },
    })
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(he.common.error)
    fail = false
    await userEvent.click(within(alert).getByRole('button', { name: he.common.retry }))
    expect(await screen.findByText(he.profile.locked)).toBeInTheDocument()
  })

  it('my own username redirects to /profile', async () => {
    const { fake } = renderAt('/u/Gal_B', {
      'GET /users/gal_b': ownProfile,
      'GET /users/gal_b/posts?lang=he': page([]),
    })
    expect(await screen.findByRole('link', { name: he.profile.editProfile })).toBeInTheDocument()
    expect(fake.log().filter((k) => k.startsWith('GET /users/'))).toEqual([
      'GET /users/gal_b',
      'GET /users/gal_b/posts?lang=he',
    ])
  })

  it('looks the username up in lower case', async () => {
    const { fake } = renderAt('/u/GAL', { 'GET /users/gal': galProfile({}) })
    expect(await screen.findByText(he.profile.locked)).toBeInTheDocument()
    expect(fake.log()).toContain('GET /users/gal')
  })

  it('following someone refreshes their profile', async () => {
    let state: UserProfile = galProfile({})
    const { fake } = renderAt('/u/gal', {
      'GET /users/gal': () => state,
      'GET /users/gal/posts?lang=he': page([{ ...POST_CARD, opinion: OPINION }]),
      'POST /follows/gal': () => {
        state = galProfile({
          follow_state: 'following',
          details: { bio: null, post_count: 1, followers_count: null, following_count: null },
        })
        return { follow_state: 'following' }
      },
    })
    await userEvent.click(await screen.findByRole('button', { name: `${he.follow.follow} Gal` }))
    expect(await screen.findByText(OPINION)).toBeInTheDocument()
    expect(screen.queryByText(he.profile.locked)).toBeNull()
    expect(fake.count('GET /users/gal')).toBe(2)
  })

  it('people search rows link to the profile', () => {
    const fake = fakeApi({})
    renderApp(
      <ul>
        <UserCardRow user={DANA} />
      </ul>,
      { api: fake.api },
    )
    expect(screen.getByRole('link', { name: 'Dana' })).toHaveAttribute('href', '/u/dana')
  })
})
