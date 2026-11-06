import { Route, Routes } from 'react-router'
import { SettingsPage } from '../me/SettingsPage'
import { Placeholder } from '../pages/Placeholder'
import { TABS } from './tabs'

export function AppRoutes() {
  return (
    <Routes>
      {TABS.map((tab) => (
        <Route key={tab.path} path={tab.path} element={<Placeholder titleKey={tab.labelKey} />} />
      ))}
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<Placeholder titleKey="nav.home" />} />
    </Routes>
  )
}
