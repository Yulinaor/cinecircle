export type FollowState = 'self' | 'none' | 'requested' | 'following'

export type UserCard = {
  username: string
  display_name: string
  avatar_url: string | null
  follow_state: FollowState
}

export type UserProfile = UserCard & {
  details: { bio: string | null; post_count: number } | null
}

export type MyProfile = {
  username: string
  display_name: string
  avatar_url: string | null
  bio: string | null
  locale: 'he' | 'en'
}

export type Me = {
  id: string
  email: string | null
  profile: MyProfile | null
}

export type NotificationItem = {
  id: number
  type: 'follow_request' | 'follow_accepted'
  actor: UserCard
  created_at: string
  read: boolean
  request_pending: boolean
}
