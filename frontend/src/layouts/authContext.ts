import { useOutletContext } from 'react-router-dom'
import type { AuthMe } from '../lib/types'

export type AuthContext = { auth: AuthMe }

/** Typed access to the signed-in user for any route rendered below a guard. */
export function useAuthContext(): AuthMe {
  return useOutletContext<AuthContext>().auth
}
