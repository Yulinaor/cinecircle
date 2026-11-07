import { Route, Routes } from 'react-router'
import { ProfileHubPage } from '../me/ProfileHubPage'
import { SettingsPage } from '../me/SettingsPage'
import { NotificationsPage } from '../notifications/NotificationsPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { Placeholder } from '../pages/Placeholder'
import { ConnectionsPage } from '../people/ConnectionsPage'
import { PeopleSearchPage } from '../people/PeopleSearchPage'
import { PostPage } from '../posts/PostPage'
import { TABS } from './tabs'

export function AppRoutes() {
  return (
    <Routes>
      {TABS.filter((tab) => tab.path !== '/profile').map((tab) => (
        <Route key={tab.path} path={tab.path} element={<Placeholder titleKey={tab.labelKey} />} />
      ))}
      <Route path="/profile" element={<ProfileHubPage />} />
      <Route path="/people" element={<PeopleSearchPage />} />
      <Route path="/connections" element={<ConnectionsPage />} />
      <Route path="/notifications" element={<NotificationsPage />} />
      <Route path="/posts/:id" element={<PostPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
