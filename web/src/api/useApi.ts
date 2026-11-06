import { createContext, useCallback, useContext } from 'react'
import { useAuth } from '../auth/AuthProvider'
import { supabase } from '../auth/supabase'
import { ApiError, apiFetch, type ApiInit } from './client'

export type ApiCall = <T>(path: string, init?: Omit<ApiInit, 'token'>) => Promise<T>

/** Lets tests (renderApp) swap the network layer; null in the real app. */
export const ApiOverrideContext = createContext<ApiCall | null>(null)

/**
 * Authenticated API caller. Reads the freshest access token per call (supabase refreshes it),
 * and on a 401 signs the user out before rethrowing.
 */
export function useApi(): ApiCall {
  const override = useContext(ApiOverrideContext)
  const { signOut } = useAuth()
  const call = useCallback(
    async <T,>(path: string, init: Omit<ApiInit, 'token'> = {}): Promise<T> => {
      const { data } = (await supabase?.auth.getSession()) ?? { data: { session: null } }
      const token = data.session?.access_token
      if (!token) {
        await signOut()
        throw new ApiError(401, 'not_authenticated')
      }
      try {
        return await apiFetch<T>(path, { ...init, token })
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) await signOut()
        throw error
      }
    },
    [signOut],
  )
  return override ?? call
}
