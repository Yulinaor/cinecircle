import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { MyProfile } from '../api/types'
import { useAuth } from '../auth/AuthProvider'
import { LanguageChoice } from './LanguageChoice'
import { useMe, useUpdateMe, type ProfileChanges } from './useMe'

const BIO_MAX = 300

const FIELD =
  'min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-base text-ink placeholder:text-muted'
const PRIMARY =
  'min-h-11 w-full rounded-xl bg-accent px-4 text-base font-semibold text-white disabled:opacity-60'
const SECONDARY =
  'min-h-11 w-full rounded-xl border border-line bg-surface px-4 text-base font-semibold text-ink hover:bg-bg disabled:opacity-60'

export function SettingsPage() {
  const { t } = useTranslation()
  const me = useMe()
  const profile = me.data?.profile
  return (
    <section className="mx-auto flex w-full max-w-sm flex-col gap-4 p-6">
      <h1 className="text-2xl font-extrabold">{t('settings.title')}</h1>
      {profile ? (
        <SettingsForm profile={profile} />
      ) : me.isError ? (
        <p role="alert" className="text-sm font-medium text-danger">
          {t('common.error')}
        </p>
      ) : (
        <p role="status" className="text-muted">
          {t('auth.loading')}
        </p>
      )}
    </section>
  )
}

function SettingsForm({ profile }: { profile: MyProfile }) {
  const { t } = useTranslation()
  const { signOut } = useAuth()
  const save = useUpdateMe()
  const languageSave = useUpdateMe()
  const [displayName, setDisplayName] = useState(profile.display_name)
  const [bio, setBio] = useState(profile.bio ?? '')

  const name = displayName.trim()
  const changes: ProfileChanges = {}
  if (name !== profile.display_name) changes.display_name = name
  if (bio.trim() !== (profile.bio ?? '')) changes.bio = bio.trim()
  const dirty = Object.keys(changes).length > 0

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!dirty || name === '') return
    save.mutate(changes)
  }

  return (
    <>
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm font-medium">
          {t('settings.displayName')}
          <input
            type="text"
            name="display_name"
            autoComplete="name"
            required
            maxLength={50}
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value)
              save.reset()
            }}
            className={FIELD}
          />
        </label>
        <div className="flex flex-col gap-1">
          <label className="flex flex-col gap-1 text-sm font-medium">
            {t('settings.bio')}
            <textarea
              name="bio"
              rows={4}
              maxLength={BIO_MAX}
              value={bio}
              aria-describedby="bio-count"
              onChange={(e) => {
                setBio(e.target.value)
                save.reset()
              }}
              className={`${FIELD} py-2`}
            />
          </label>
          <span id="bio-count" className="text-xs text-muted">
            {t('settings.bioCount', { length: bio.length, max: BIO_MAX })}
          </span>
        </div>
        {save.isError && (
          <p role="alert" className="text-sm font-medium text-danger">
            {t('common.error')}
          </p>
        )}
        {save.isSuccess && !dirty && (
          <p role="status" className="text-sm font-medium text-ink">
            {t('settings.saved')}
          </p>
        )}
        <button type="submit" disabled={!dirty || name === '' || save.isPending} className={PRIMARY}>
          {t('settings.save')}
        </button>
      </form>
      <LanguageChoice
        label={t('settings.language')}
        onChange={(locale) => languageSave.mutate({ locale })}
      />
      {languageSave.isError && (
        <p role="alert" className="text-sm font-medium text-danger">
          {t('common.error')}
        </p>
      )}
      <button type="button" onClick={() => void signOut()} className={SECONDARY}>
        {t('auth.signOut')}
      </button>
    </>
  )
}
