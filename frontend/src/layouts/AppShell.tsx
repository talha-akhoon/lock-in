import {
  Activity,
  CalendarCheck,
  CircleUserRound,
  Ellipsis,
  LayoutDashboard,
  Settings,
  ShieldCheck,
  Target,
  Trophy,
  Users,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { NotificationBell } from '../components/NotificationBell'
import { useAuthContext, type AuthContext } from './authContext'
import { NoChallengePage } from '../pages/NoChallengePage'

const PHONE_QUERY = '(max-width: 900px)'

const PRIMARY_TABS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/check-in', label: 'Check-in', icon: CalendarCheck },
  { to: '/goals', label: 'Goals', icon: Target },
  { to: '/team', label: 'Team', icon: Users },
] as const

const MORE_PATHS = ['/activity', '/settings', '/admin', '/results']

function isMorePath(pathname: string) {
  return MORE_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`))
}

function sidebarItems(preStart: boolean) {
  return [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, primary: true },
    {
      to: '/check-in',
      label: preStart ? 'Starting point' : "Today's Check-In",
      icon: CalendarCheck,
      primary: true,
    },
    { to: '/goals', label: 'My Goals', icon: Target, primary: true },
    { to: '/team', label: 'Team', icon: Users, primary: true },
    { to: '/activity', label: 'Activity', icon: Activity, primary: false },
  ]
}

/** True when the signed-in chrome should use a tab bar instead of a permanent sidebar. */
function usePhoneShell() {
  const [phone, setPhone] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(PHONE_QUERY).matches : false,
  )
  useEffect(() => {
    const media = window.matchMedia(PHONE_QUERY)
    function sync() {
      setPhone(media.matches)
    }
    sync()
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [])
  return phone
}

export function AppShell() {
  const auth = useAuthContext()
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const phone = usePhoneShell()
  const completed = auth.challenge_status === 'COMPLETED'
  const preStart = auth.challenge_status === 'UPCOMING'
  const moreActive = isMorePath(location.pathname)
  // Once the challenge is over there is nothing left to submit, so nudging
  // someone towards the wizard would only send them to a dead end.
  const needsGoals =
    Boolean(auth.challenge_id) && !completed && !auth.goals_committed_at && !auth.goals_locked

  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!open || !phone) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [open, phone])

  return (
    <div className="app-shell">
      {phone && open && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-hidden="true"
          tabIndex={-1}
          onClick={() => setOpen(false)}
        />
      )}
      <aside className={open ? 'sidebar open' : 'sidebar'} inert={phone && !open ? true : undefined}>
        <div className="brand">
          <span>LI</span> LockIn
        </div>
        {phone && (
          <button type="button" className="close-menu" onClick={() => setOpen(false)} aria-label="Close menu">
            <X />
          </button>
        )}
        <nav aria-label="Menu">
          {sidebarItems(preStart).map(({ to, label, icon: Icon, primary }) => (
            <NavLink
              key={to}
              to={to}
              className={primary ? 'sidebar-primary' : undefined}
              onClick={() => setOpen(false)}
            >
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
          <span className="topbar-title">{auth.team?.name}</span>
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
        {phone && (
          <nav className="tabbar" aria-label="Primary">
            {PRIMARY_TABS.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to}>
                <Icon />
                {label}
              </NavLink>
            ))}
            <button
              type="button"
              className={moreActive || open ? 'active' : undefined}
              aria-label="More"
              aria-expanded={open}
              aria-current={moreActive ? 'page' : undefined}
              onClick={() => setOpen((value) => !value)}
            >
              <Ellipsis />
              More
            </button>
          </nav>
        )}
      </div>
    </div>
  )
}
