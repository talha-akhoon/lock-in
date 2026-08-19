import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { GoalsPage } from './GoalsPage'
import { makeAuth, makeMyGoals } from '../test/factories'
import { mockFetch, renderWithAuth } from '../test/harness'

describe('goals page empty state', () => {
  it('offers Add goal, not the wizard, when locked with no goals', async () => {
    // The window can close before a member adds anything; the wizard would just
    // redirect them away, so the empty state must point at the real add path.
    mockFetch({ 'GET /me/goals': makeMyGoals([], { goals_locked: true }) })
    renderWithAuth(<GoalsPage />, makeAuth({ challenge_status: 'ACTIVE', goals_locked: true }))

    expect(await screen.findByText('No goals yet')).toBeInTheDocument()
    expect(screen.queryByText('Open the goal wizard')).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /add goal/i }).length).toBeGreaterThan(0)
  })

  it('offers the wizard when unlocked with no goals', async () => {
    mockFetch({ 'GET /me/goals': makeMyGoals([]) })
    renderWithAuth(<GoalsPage />, makeAuth({ challenge_status: 'ACTIVE' }))

    expect(await screen.findByText('No goals yet')).toBeInTheDocument()
    expect(screen.getByText('Open the goal wizard')).toBeInTheDocument()
  })
})
