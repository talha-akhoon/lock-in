import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DashboardPage } from './DashboardPage'
import {
  CHALLENGE_ID,
  USER_ID,
  makeAuth,
  makeChallenge,
  makeDashboard,
  makeMemberCard,
} from '../test/factories'
import { httpError, mockFetch, renderWithAuth } from '../test/harness'
import type { Dashboard } from '../lib/types'

function stub(dashboard: Dashboard, challenge = makeChallenge()) {
  mockFetch({
    'GET /challenges/current': challenge,
    [`GET /challenges/${CHALLENGE_ID}/dashboard`]: dashboard,
    'GET /me/notifications': { unread_count: 0, notifications: [] },
  })
}

describe('dashboard', () => {
  it('ranks members by progress', async () => {
    stub(
      makeDashboard([
        makeMemberCard({ display_name: 'Yusuf Khan', overall_progress: 71 }),
        makeMemberCard({ user_id: USER_ID, display_name: 'Sam Ali', overall_progress: 40, is_self: true }),
      ]),
    )
    renderWithAuth(<DashboardPage />, makeAuth())

    expect(await screen.findByText('#1 in the team')).toBeInTheDocument()
    expect(screen.getByText('#2 in the team · You')).toBeInTheDocument()
  })

  it('flags a member who has not submitted goals and hides their score', async () => {
    stub(
      makeDashboard([
        makeMemberCard({
          display_name: 'Yusuf Khan',
          goals_submitted: false,
          goals_locked: true,
          goals_committed: 0,
          overall_progress: 0,
        }),
      ]),
    )
    renderWithAuth(<DashboardPage />, makeAuth())

    expect(await screen.findByText('Goals not submitted')).toBeInTheDocument()
    expect(screen.getByText('The deadline passed with nothing committed.')).toBeInTheDocument()
    expect(screen.queryByText(/in the team/)).not.toBeInTheDocument()
  })

  it('offers the wizard when it is your own goals that are missing', async () => {
    stub(
      makeDashboard([
        makeMemberCard({
          user_id: USER_ID,
          display_name: 'Sam Ali',
          is_self: true,
          goals_submitted: false,
          goals_locked: false,
        }),
      ]),
    )
    renderWithAuth(<DashboardPage />, makeAuth())

    expect(await screen.findByRole('link', { name: /set my goals/i })).toBeInTheDocument()
    expect(screen.getByText('Still inside the submission window.')).toBeInTheDocument()
  })

  it('never shows a teammate’s goal titles', async () => {
    stub(makeDashboard([makeMemberCard({ display_name: 'Yusuf Khan' })]))
    renderWithAuth(<DashboardPage />, makeAuth())

    await screen.findByText('Yusuf Khan')
    expect(screen.getByText('1/4 done')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('Deadlift')
  })

  it('points to the results once the challenge is over', async () => {
    stub(makeDashboard([]), makeChallenge({ status: 'COMPLETED', days_remaining: 0 }))
    renderWithAuth(<DashboardPage />, makeAuth({ challenge_status: 'COMPLETED' }))

    expect(await screen.findByText('The challenge is over')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /view results/i })).toBeInTheDocument()
  })

  it('shows the start date rather than a day count before kick-off', async () => {
    stub(makeDashboard([]), makeChallenge({ status: 'UPCOMING', day_number: 0 }))
    renderWithAuth(<DashboardPage />, makeAuth({ challenge_status: 'UPCOMING' }))

    expect(await screen.findByText(/^Starts /)).toBeInTheDocument()
  })

  it('points a committed member at the starting-point form before kick-off', async () => {
    stub(makeDashboard([]), makeChallenge({ status: 'UPCOMING', day_number: 0 }))
    renderWithAuth(
      <DashboardPage />,
      makeAuth({
        challenge_status: 'UPCOMING',
        goals_locked: true,
        goals_committed_at: '2026-01-03T00:00:00Z',
      }),
    )

    expect(await screen.findByText('Record your starting point')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /starting point/i })).toHaveAttribute(
      'href',
      '/check-in',
    )
  })

  it('treats no challenge as a normal state, not a failure', async () => {
    mockFetch({ 'GET /challenges/current': httpError(404, 'No challenge yet') })
    renderWithAuth(<DashboardPage />, makeAuth())

    expect(await screen.findByText('No challenge yet')).toBeInTheDocument()
    expect(screen.getByText('Waiting on your admin')).toBeInTheDocument()
  })

  it('offers an admin the way to create one', async () => {
    mockFetch({ 'GET /challenges/current': httpError(404, 'No challenge yet') })
    renderWithAuth(<DashboardPage />, makeAuth({ role: 'ADMIN' }))

    expect(await screen.findByRole('link', { name: /create the challenge/i })).toBeInTheDocument()
  })

  it('still reports a genuine server failure', async () => {
    mockFetch({ 'GET /challenges/current': httpError(500, 'Database is down') })
    renderWithAuth(<DashboardPage />, makeAuth())

    expect(await screen.findByText('Database is down')).toBeInTheDocument()
  })
})
