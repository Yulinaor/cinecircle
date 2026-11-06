import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const url = String(import.meta.env.VITE_SUPABASE_URL ?? '').trim()
const publishableKey = String(import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ?? '').trim()

/** Browser-safe client (publishable key only). Null when the env vars are blank, so the app can say so. */
export const supabase: SupabaseClient | null =
  url && publishableKey ? createClient(url, publishableKey) : null
