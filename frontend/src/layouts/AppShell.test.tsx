import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Outlet, Route } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { makeAuth } from '../test/factories'
import { mockFetch, renderRoutes } from '../test/harness'
import type { AuthMe } from '../lib/types'
import { AppShell } from './AppShell'
import type { AuthContext } from './authContext'

function stub() {
  mockFetch({
    'GET /me/notifications': { unread_count: 0, notifications: [] },
  })
}

function tree(auth: AuthMe) {
  return (
    <Route element={<Outlet context={{ auth } satisfies AuthContext} />}>
      <Route element={<AppShell />}>
        <Route path="/dashboard" element={<h1>Dashboard</h1>} />
        <Route path="/check-in" element={<h1>Check-in</h1>} />
        <Route path="/goals" element={<h1>Goals</h1>} />
        <Route path="/team" element={<h1>Team</h1>} />
        <Route path="/activity" element={<h1>Activity</h1>} />
        <Route path="/settings" element={<h1>Settings</h1>} />
        <Route path="/admin" element={<h1>Admin</h1>} />
        <Route path="/results" element={<h1>Results</h1>} />
      </Route>
    </Route>
  )
}

function mockPhone(phone: boolean) {
  vi.spyOn(window, 'matchMedia').mockImplementation((query: string) =>
    ({
      matches: phone && query.includes('max-width: 900px'),
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }) as MediaQueryList,
  )
}

describe('app shell', () => {
  it('keeps the full sidebar on a wide screen', async () => {
    stub()
    mockPhone(false)
    renderRoutes(tree(makeAuth()), '/dashboard')

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: "Today's Check-In" })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'My Goals' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Activity' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Close menu' })).not.toBeInTheDocument()
  })

  it('exposes a phone tab bar for the daily screens', async () => {
    stub()
    mockPhone(true)
    renderRoutes(tree(makeAuth()), '/dashboard')

    const tabs = await screen.findByRole('navigation', { name: 'Primary' })
    expect(within(tabs).getByRole('link', { name: 'Dashboard' })).toBeInTheDocument()
    expect(within(tabs).getByRole('link', { name: 'Check-in' })).toBeInTheDocument()
    expect(within(tabs).getByRole('link', { name: 'Goals' })).toBeInTheDocument()
    expect(within(tabs).getByRole('link', { name: 'Team' })).toBeInTheDocument()
    expect(within(tabs).getByRole('button', { name: 'More' })).toBeInTheDocument()
  })

  it('opens Activity, Settings and Admin from More on a phone', async () => {
    stub()
    mockPhone(true)
    renderRoutes(tree(makeAuth({ role: 'ADMIN' })), '/dashboard')
    const user = userEvent.setup()

    const more = await screen.findByRole('button', { name: 'More' })
    await user.click(more)
    const menu = screen.getByRole('navigation', { name: 'Menu' })
    expect(within(menu).getByRole('link', { name: 'Activity' })).toBeInTheDocument()
    expect(within(menu).getByRole('link', { name: 'Settings' })).toBeInTheDocument()
    expect(within(menu).getByRole('link', { name: 'Admin' })).toBeInTheDocument()
    expect(more).toHaveAttribute('aria-expanded', 'true')

    await user.click(screen.getByRole('button', { name: 'Close menu' }))
    expect(more).toHaveAttribute('aria-expanded', 'false')
  })

  it('keeps the check-in tab short before kick-off', async () => {
    stub()
    mockPhone(true)
    renderRoutes(tree(makeAuth({ challenge_status: 'UPCOMING' })), '/dashboard')

    const tabs = await screen.findByRole('navigation', { name: 'Primary' })
    expect(within(tabs).getByRole('link', { name: 'Check-in' })).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: 'More' }))
    expect(screen.getByRole('link', { name: 'Starting point' })).toBeInTheDocument()
  })

  it('shows Results in More once the challenge has finished', async () => {
    stub()
    mockPhone(true)
    renderRoutes(tree(makeAuth({ challenge_status: 'COMPLETED' })), '/dashboard')

    await userEvent.setup().click(await screen.findByRole('button', { name: 'More' }))
    expect(screen.getByRole('link', { name: 'Results' })).toBeInTheDocument()
  })
})
