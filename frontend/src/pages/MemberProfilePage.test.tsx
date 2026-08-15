import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemberProfilePage } from './MemberProfilePage'
import {
  OTHER_ID,
  TEAM_ID,
  makeAuth,
  makeGoal,
  makeHeatmap,
  makeMemberProfile,
} from '../test/factories'
import { httpError, mockFetch, renderWithAuth } from '../test/harness'

const auth = makeAuth()
const route = `/team/members/${OTHER_ID}`
const path = '/team/members/:userId'

function render(profile: unknown) {
  mockFetch({ [`GET /teams/${TEAM_ID}/members/${OTHER_ID}`]: profile })
  return renderWithAuth(<MemberProfilePage />, auth, { route, path })
}

describe('member profile privacy', () => {
  it('never names a teammate’s private goals, only counts them', async () => {
    render(
      makeMemberProfile({
        goals: [makeGoal({ title: 'Deadlift 120kg' })],
        private_committed: 2,
        private_completed: 1,
        goals_committed: 3,
        goals_completed: 2,
      }),
    )

    expect(await screen.findByText('Deadlift 120kg')).toBeInTheDocument()
    expect(screen.getByText(/2 private goals counted towards the score/i)).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('Something personal')
  })

  it('still counts private goals in the headline score', async () => {
    render(
      makeMemberProfile({
        goals: [],
        private_committed: 2,
        private_completed: 2,
        overall_progress: 100,
      }),
    )

    expect(await screen.findByText('100%')).toBeInTheDocument()
    expect(screen.getByText('Every goal they committed to is private.')).toBeInTheDocument()
  })

  it('does not link to a teammate’s goal detail, which they cannot open', async () => {
    render(makeMemberProfile({ is_self: false, goals: [makeGoal({ title: 'Deadlift 120kg' })] }))
    expect((await screen.findByText('Deadlift 120kg')).closest('a')).toBeNull()
  })

  it('links straight to goal detail on your own profile', async () => {
    render(makeMemberProfile({ is_self: true, goals: [makeGoal({ title: 'Deadlift 120kg' })] }))
    expect((await screen.findByText('Deadlift 120kg')).closest('a')).not.toBeNull()
  })
})

describe('member profile states', () => {
  it('renders the heatmap over the challenge window, not a fixed 184 days', async () => {
    render(
      makeMemberProfile({
        heatmap: makeHeatmap({
          start_date: '2026-01-01',
          end_date: '2026-04-10',
          today: '2026-02-01',
        }),
      }),
    )
    const cells = await screen.findAllByTestId('heatmap-cell')
    expect(cells).toHaveLength(100)
  })

  it('flags a member who never submitted goals', async () => {
    render(
      makeMemberProfile({
        goals: [],
        goals_committed: 0,
        private_committed: 0,
        goals_locked: true,
      }),
    )
    expect(await screen.findByText('Goals not submitted')).toBeInTheDocument()
    expect(
      screen.getByText('The submission deadline passed with nothing committed.'),
    ).toBeInTheDocument()
  })

  it('shows a not-found state for an unknown member instead of loading forever', async () => {
    render(httpError(404, 'Member not found'))
    expect(await screen.findByText('Member not found')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
