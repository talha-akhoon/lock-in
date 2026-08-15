import { screen } from '@testing-library/react'
import { Navigate, Outlet, Route } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { RequireAdmin, RequireAuth, RequireTeam } from './guards'
import { makeAuth } from '../test/factories'
import { httpError, mockFetch, renderRoutes } from '../test/harness'

const tree = (
  <>
    <Route path="/login" element={<h1>Sign in</h1>} />
    <Route path="/dashboard" element={<h1>Dashboard</h1>} />
    <Route element={<RequireAuth />}>
      <Route path="/onboarding/start" element={<h1>Start</h1>} />
      <Route element={<RequireTeam />}>
        <Route path="/goals" element={<h1>My goals</h1>} />
        <Route element={<RequireAdmin />}>
          <Route path="/admin/members" element={<h1>Admin members</h1>} />
        </Route>
      </Route>
    </Route>
  </>
)

describe('route guards', () => {
  it('sends an unauthenticated visitor to sign in', async () => {
    mockFetch({ 'GET /auth/me': httpError(401, 'Sign in required') })
    renderRoutes(tree, '/goals')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('guards onboarding too, so redeeming an invite cannot fail silently', async () => {
    mockFetch({ 'GET /auth/me': httpError(401, 'Sign in required') })
    renderRoutes(tree, '/onboarding/start')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('sends a signed-in visitor with no team into onboarding', async () => {
    mockFetch({ 'GET /auth/me': makeAuth({ team: null, role: null, challenge_id: null }) })
    renderRoutes(tree, '/goals')
    expect(await screen.findByRole('heading', { name: 'Start' })).toBeInTheDocument()
  })

  it('lets a member reach member routes', async () => {
    mockFetch({ 'GET /auth/me': makeAuth() })
    renderRoutes(tree, '/goals')
    expect(await screen.findByRole('heading', { name: 'My goals' })).toBeInTheDocument()
  })

  it('bounces a member away from admin routes', async () => {
    mockFetch({ 'GET /auth/me': makeAuth({ role: 'MEMBER' }) })
    renderRoutes(tree, '/admin/members')
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Admin members' })).not.toBeInTheDocument()
  })

  it('lets an admin through', async () => {
    mockFetch({ 'GET /auth/me': makeAuth({ role: 'ADMIN' }) })
    renderRoutes(tree, '/admin/members')
    expect(await screen.findByRole('heading', { name: 'Admin members' })).toBeInTheDocument()
  })

  it('shows a loading state while the session is being checked', () => {
    mockFetch({ 'GET /auth/me': makeAuth() })
    renderRoutes(tree, '/goals')
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})

describe('legacy routes', () => {
  it('keeps the old invitation path working', async () => {
    mockFetch({ 'GET /auth/me': makeAuth({ team: null, role: null }) })
    renderRoutes(
      <>
        <Route element={<RequireAuth />}>
          <Route
            path="/onboarding/invitation"
            element={<Navigate to="/onboarding/start" replace />}
          />
          <Route path="/onboarding/start" element={<h1>Start</h1>} />
          <Route element={<Outlet />} />
        </Route>
      </>,
      '/onboarding/invitation',
    )
    expect(await screen.findByRole('heading', { name: 'Start' })).toBeInTheDocument()
  })
})
