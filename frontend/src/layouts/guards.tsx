import { Navigate, Outlet } from 'react-router-dom'
import { Loading } from '../components/primitives'
import { useAuth } from '../hooks/queries'
import { useAuthContext, type AuthContext } from './authContext'

export function RequireAuth() {
  const auth = useAuth()
  if (auth.isLoading) return <Loading label="Checking your session" />
  if (!auth.data) return <Navigate to="/login" replace />
  return <Outlet context={{ auth: auth.data } satisfies AuthContext} />
}

/** Everything past the first onboarding step needs a team. */
export function RequireTeam() {
  const auth = useAuthContext()
  if (!auth.team) return <Navigate to="/onboarding/start" replace />
  return <Outlet context={{ auth } satisfies AuthContext} />
}

export function RequireAdmin() {
  const auth = useAuthContext()
  if (auth.role !== 'ADMIN') return <Navigate to="/dashboard" replace />
  return <Outlet context={{ auth } satisfies AuthContext} />
}
