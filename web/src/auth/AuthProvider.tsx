import type { Session } from '@supabase/supabase-js'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { supabase } from './supabase'

export type AuthState = {
  status: 'loading' | 'signed_out' | 'signed_in'
  session: Session | null
  signOut(): Promise<void>
}

// Context and hook live beside the provider on purpose (single import path for consumers and tests).
// oxlint-disable-next-line react/only-export-components
export const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(supabase !== null)

  useEffect(() => {
    if (!supabase) return
    let active = true
    void supabase.auth
      .getSession()
      .then(({ data }) => {
        if (active) setSession((current) => current ?? data.session)
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false)
      })
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return
      setSession(next)
      setLoading(false)
    })
    return () => {
      active = false
      data.subscription.unsubscribe()
    }
  }, [])

  const signOut = useCallback(async () => {
    try {
      await supabase?.auth.signOut()
    } finally {
      setSession(null)
    }
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      status: loading ? 'loading' : session ? 'signed_in' : 'signed_out',
      session,
      signOut,
    }),
    [loading, session, signOut],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// oxlint-disable-next-line react/only-export-components
export function useAuth(): AuthState {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}
