import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { ApiStatus } from './app/ApiStatus'
import { AppShell } from './app/AppShell'
import { AuthProvider } from './auth/AuthProvider'
import { initI18n } from './i18n'
import './theme/tokens.css'

initI18n()

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AppShell status={<ApiStatus />} />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
