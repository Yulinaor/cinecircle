import { useId } from 'react'

/**
 * Props that name a row's action button "<visible text> <person>" ("Accept Dana", "אישור Dana"),
 * so identical buttons in a list are told apart. Without a person to refer to, the visible text
 * alone is the name.
 */
export function useActionName(personNameId: string | undefined) {
  const id = useId()
  return personNameId ? { id, 'aria-labelledby': `${id} ${personNameId}` } : {}
}
