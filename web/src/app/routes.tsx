import { Route, Routes } from 'react-router'
import { ProfileHubPage } from '../me/ProfileHubPage'
import { SettingsPage } from '../me/SettingsPage'
import { NotificationsPage } from '../notifications/NotificationsPage'
import { Placeholder } from '../pages/Placeholder'
import { ConnectionsPage } from '../people/ConnectionsPage'
import { PeopleSearchPage } from '../people/PeopleSearchPage'
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
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<Placeholder titleKey="nav.home" />} />
    </Routes>
  )
}
