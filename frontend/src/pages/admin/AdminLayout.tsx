import { NavLink, Outlet } from 'react-router-dom'
import { PageHeader } from '../../components/primitives'
import { useAuthContext, type AuthContext } from '../../layouts/authContext'

const TABS = [
  { to: '/admin/team', label: 'Team' },
  { to: '/admin/challenge', label: 'Challenge' },
  { to: '/admin/invitations', label: 'Invitations' },
  { to: '/admin/members', label: 'Members' },
  { to: '/admin/audit', label: 'Audit log' },
]

export function AdminLayout() {
  const auth = useAuthContext()
  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Team controls"
        description="Manage access, the challenge, and the commitment contract. Every change is recorded."
      />
      <nav className="tabs">
        {TABS.map((tab) => (
          <NavLink key={tab.to} to={tab.to}>
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <Outlet context={{ auth } satisfies AuthContext} />
    </>
  )
}
