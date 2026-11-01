/** Bottom navigation, in display order (spec 01 §5). */
export const TABS = [
  { path: '/', labelKey: 'nav.home' },
  { path: '/discover', labelKey: 'nav.discover' },
  { path: '/post', labelKey: 'nav.post' },
  { path: '/wishlist', labelKey: 'nav.wishlist' },
  { path: '/profile', labelKey: 'nav.profile' },
] as const
