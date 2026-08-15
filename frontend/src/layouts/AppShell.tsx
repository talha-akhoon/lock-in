import {
  Activity,
  CalendarCheck,
  CircleUserRound,
  LayoutDashboard,
  Menu,
  Settings,
  ShieldCheck,
  Target,
  Trophy,
  Users,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { NotificationBell } from '../components/NotificationBell'
import { useAuthContext, type AuthContext } from './authContext'
import { NoChallengePage } from '../pages/NoChallengePage'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/check-in', label: "Today's Check-In", icon: CalendarCheck },
  { to: '/goals', label: 'My Goals', icon: Target },
  { to: '/team', label: 'Team', icon: Users },
  { to: '/activity', label: 'Activity', icon: Activity },
]

export function AppShell() {
  const auth = useAuthContext()
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const completed = auth.challenge_status === 'COMPLETED'
  // Once the challenge is over there is nothing left to submit, so nudging
  // someone towards the wizard would only send them to a dead end.
  const needsGoals =
    Boolean(auth.challenge_id) && !completed && !auth.goals_committed_at && !auth.goals_locked

  return (
    <div className="app-shell">
      <aside className={open ? 'sidebar open' : 'sidebar'}>
        <div className="brand">
          <span>LI</span> LockIn
        </div>
        <button className="close-menu" onClick={() => setOpen(false)} aria-label="Close menu">
          <X />
        </button>
        <nav>
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} onClick={() => setOpen(false)}>
              <Icon /> {label}
            </NavLink>
          ))}
          {completed && (
            <NavLink to="/results" onClick={() => setOpen(false)}>
              <Trophy /> Results
            </NavLink>
          )}
          {auth.role === 'ADMIN' && (
            <>
              <div className="nav-label">Administration</div>
              <NavLink to="/admin" onClick={() => setOpen(false)}>
                <ShieldCheck /> Admin
              </NavLink>
            </>
          )}
        </nav>
        <div className="sidebar-bottom">
          <NavLink to="/settings" onClick={() => setOpen(false)}>
            <Settings /> Settings
          </NavLink>
          <div className="user-chip">
            {auth.user.avatar_url ? (
              <img src={auth.user.avatar_url} alt="" />
            ) : (
              <CircleUserRound />
            )}
            <div>
              <b>{auth.user.display_name}</b>
              <span>{auth.role}</span>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <button className="menu-button" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu />
          </button>
          <span>{auth.team?.name}</span>
          <NotificationBell />
        </header>
        <main className="content">
          {needsGoals && !location.pathname.startsWith('/goals') && (
            <div className="nudge">
              <Target />
              <div>
                <b>Your commitment isn't locked in yet</b>
                <span>Define your goals before the deadline passes.</span>
              </div>
              <Link className="primary" to="/onboarding/goals">
                Set my goals
              </Link>
            </div>
          )}
          {auth.challenge_id ? (
            <Outlet context={{ auth } satisfies AuthContext} />
          ) : (
            <NoChallengePage />
          )}
        </main>
      </div>
    </div>
  )
}
