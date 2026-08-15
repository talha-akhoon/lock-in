import { LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Avatar, PageHeader, Pill } from '../components/primitives'
import { useLogout } from '../hooks/queries'
import { formatDateTime } from '../lib/format'
import { useAuthContext } from '../layouts/authContext'

export function SettingsPage() {
  const auth = useAuthContext()
  const logout = useLogout()
  const navigate = useNavigate()

  return (
    <>
      <PageHeader eyebrow="Account" title="Settings" description="Your identity and session." />
      <section className="card settings-identity">
        <Avatar name={auth.user.display_name} url={auth.user.avatar_url} size="lg" />
        <div>
          <b>{auth.user.display_name}</b>
          <span>{auth.user.email}</span>
        </div>
        {auth.role && <Pill tone={auth.role === 'ADMIN' ? 'good' : undefined}>{auth.role}</Pill>}
      </section>

      <section className="card admin-section">
        <h2>Your commitment</h2>
        <div className="admin-row">
          <b>Team</b>
          <span>{auth.team?.name ?? 'None'}</span>
        </div>
        <div className="admin-row">
          <b>Goals locked</b>
          <span>{auth.goals_locked ? 'Yes' : 'Not yet'}</span>
        </div>
        {auth.goals_committed_at ? (
          <div className="admin-row">
            <b>Committed at</b>
            <span>{formatDateTime(auth.goals_committed_at)}</span>
          </div>
        ) : (
          auth.goals_due_at && (
            <div className="admin-row">
              <b>Goals due</b>
              <span>{formatDateTime(auth.goals_due_at)}</span>
            </div>
          )
        )}
      </section>

      <button
        className="danger"
        disabled={logout.isPending}
        onClick={async () => {
          await logout.mutateAsync()
          navigate('/login', { replace: true })
        }}
      >
        <LogOut /> Sign out
      </button>
    </>
  )
}
