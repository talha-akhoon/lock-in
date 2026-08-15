import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AdminInvitationsPage } from './AdminInvitationsPage'
import { AdminMembersPage } from './AdminMembersPage'
import { AdminAuditPage } from './AdminAuditPage'
import {
  CHALLENGE_ID,
  OTHER_ID,
  TEAM_ID,
  USER_ID,
  makeAuth,
  makeTeamMember,
} from '../../test/factories'
import { httpError, mockFetch, renderWithAuth } from '../../test/harness'
import type { Invitation, ParticipantRow, TeamMember } from '../../lib/types'

const admin = makeAuth({ role: 'ADMIN' })

function invitation(overrides: Partial<Invitation> = {}): Invitation {
  return {
    id: 'inv-1',
    code_prefix: 'ABCD',
    expires_at: null,
    max_uses: 1,
    use_count: 0,
    revoked_at: null,
    created_at: '2026-01-02T10:00:00Z',
    ...overrides,
  }
}

function participant(overrides: Partial<ParticipantRow> = {}): ParticipantRow {
  return {
    participant_id: 'p1',
    challenge_id: CHALLENGE_ID,
    challenge_name: 'Six-Month Lock-In',
    user_id: OTHER_ID,
    display_name: 'Yusuf Khan',
    status: 'ACTIVE',
    goals_due_at: '2026-01-06T00:00:00Z',
    goals_locked_at: null,
    goals_committed_at: null,
    goals_committed: 0,
    first_goal_id: null,
    ...overrides,
  }
}

describe('admin invitations', () => {
  it('shows a new code once and only stores its prefix', async () => {
    const fetchMock = mockFetch({
      [`GET /teams/${TEAM_ID}/invitations`]: [invitation()],
      [`POST /teams/${TEAM_ID}/invitations`]: invitation({ id: 'inv-2', code: 'WXYZ-2345' }),
    })
    renderWithAuth(<AdminInvitationsPage />, admin)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /new invitation/i }))

    expect(await screen.findByText('WXYZ-2345')).toBeInTheDocument()
    expect(screen.getByText(/cannot be shown again/i)).toBeInTheDocument()
    expect(fetchMock.sent(`POST /teams/${TEAM_ID}/invitations`)[0].body).toEqual({
      max_uses: 1,
      expires_at: null,
    })
  })

  it('labels a spent code as used up and hides its revoke button', async () => {
    mockFetch({
      [`GET /teams/${TEAM_ID}/invitations`]: [invitation({ use_count: 1, max_uses: 1 })],
    })
    renderWithAuth(<AdminInvitationsPage />, admin)

    expect(await screen.findByText('Used up')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /revoke abcd/i })).not.toBeInTheDocument()
  })

  it('confirms before revoking a live code', async () => {
    const fetchMock = mockFetch({
      [`GET /teams/${TEAM_ID}/invitations`]: [invitation({ max_uses: 5 })],
      [`DELETE /teams/${TEAM_ID}/invitations/inv-1`]: undefined,
    })
    renderWithAuth(<AdminInvitationsPage />, admin)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /revoke abcd/i }))
    expect(fetchMock.sent(`DELETE /teams/${TEAM_ID}/invitations/inv-1`)).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: 'Revoke' }))
    await waitFor(() =>
      expect(fetchMock.sent(`DELETE /teams/${TEAM_ID}/invitations/inv-1`)).toHaveLength(1),
    )
  })
})

function stubMembers(members: TeamMember[], participants: ParticipantRow[] = []) {
  return mockFetch({
    [`GET /teams/${TEAM_ID}/members`]: members,
    [`GET /teams/${TEAM_ID}/participants`]: participants,
    [`PATCH /teams/${TEAM_ID}/members/${OTHER_ID}`]: makeTeamMember({ role: 'ADMIN' }),
    [`DELETE /teams/${TEAM_ID}/members/${OTHER_ID}`]: undefined,
    'POST /goals/goal-x/unlock': { unlocked_until: '2026-01-08T00:00:00Z', user_id: OTHER_ID },
  })
}

describe('admin members', () => {
  const self = makeTeamMember({
    id: USER_ID,
    display_name: 'Sam Ali',
    email: 'sam@example.com',
    role: 'ADMIN',
  })
  const other = makeTeamMember()

  it('promotes a member to admin', async () => {
    const fetchMock = stubMembers([self, other])
    renderWithAuth(<AdminMembersPage />, admin)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /promote/i }))
    await waitFor(() =>
      expect(fetchMock.sent(`PATCH /teams/${TEAM_ID}/members/${OTHER_ID}`)).toHaveLength(1),
    )
    expect(fetchMock.sent(`PATCH /teams/${TEAM_ID}/members/${OTHER_ID}`)[0].body).toEqual({
      role: 'ADMIN',
    })
  })

  it('will not let the only admin demote or remove themselves', async () => {
    stubMembers([self, other])
    renderWithAuth(<AdminMembersPage />, admin)

    const ownRow = (await screen.findByText('sam@example.com')).closest(
      '.member-row',
    ) as HTMLElement
    expect(within(ownRow).queryByRole('button', { name: /demote/i })).not.toBeInTheDocument()
    expect(within(ownRow).queryByRole('button', { name: /remove/i })).not.toBeInTheDocument()

    const otherRow = screen.getByText('yusuf@example.com').closest('.member-row') as HTMLElement
    expect(within(otherRow).getByRole('button', { name: /promote/i })).toBeInTheDocument()
    expect(within(otherRow).getByRole('button', { name: /remove/i })).toBeInTheDocument()
  })

  it('confirms an unlock override and explains it is audited', async () => {
    const fetchMock = stubMembers(
      [self, other],
      [participant({ goals_locked_at: '2026-01-06T00:00:00Z', goals_committed: 3, first_goal_id: 'goal-x' })],
    )
    renderWithAuth(<AdminMembersPage />, admin)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /unlock/i }))
    expect(screen.getByText(/recorded in the audit log against your name/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /unlock for 24 hours/i }))
    await waitFor(() => expect(fetchMock.sent('POST /goals/goal-x/unlock')).toHaveLength(1))
  })

  it('offers no unlock for someone who never locked in', async () => {
    stubMembers([self, other], [participant()])
    renderWithAuth(<AdminMembersPage />, admin)

    await screen.findByText('Yusuf Khan')
    expect(screen.queryByRole('button', { name: /unlock/i })).not.toBeInTheDocument()
  })

  it('reports a refused removal instead of failing quietly', async () => {
    mockFetch({
      [`GET /teams/${TEAM_ID}/members`]: [self, other],
      [`GET /teams/${TEAM_ID}/participants`]: [],
      [`DELETE /teams/${TEAM_ID}/members/${OTHER_ID}`]: httpError(
        409,
        'Admins cannot remove themselves',
      ),
    })
    renderWithAuth(<AdminMembersPage />, admin)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /remove/i }))
    await user.click(screen.getByRole('button', { name: /remove member/i }))
    expect(await screen.findByText('Admins cannot remove themselves')).toBeInTheDocument()
  })
})

describe('audit log', () => {
  it('names the actor and describes the action in plain words', async () => {
    mockFetch({
      [`GET /teams/${TEAM_ID}/audit-logs`]: [
        {
          id: 'a1',
          actor_user_id: USER_ID,
          actor: 'Sam Ali',
          action: 'CHALLENGE_FORFEIT_CHANGED',
          entity_type: 'challenge',
          entity_id: CHALLENGE_ID,
          metadata: { from: 20000, to: 25000 },
          created_at: '2026-01-05T09:00:00Z',
        },
      ],
    })
    renderWithAuth(<AdminAuditPage />, admin)

    expect(await screen.findByText('Sam Ali changed the forfeit')).toBeInTheDocument()
    expect(screen.getByText('from: 20000 · to: 25000')).toBeInTheDocument()
  })

  it('still names an actor who has since left the team', async () => {
    mockFetch({
      [`GET /teams/${TEAM_ID}/audit-logs`]: [
        {
          id: 'a2',
          actor_user_id: OTHER_ID,
          actor: 'Departed Admin',
          action: 'MEMBER_REMOVED',
          entity_type: 'team_member',
          entity_id: USER_ID,
          metadata: null,
          created_at: '2026-01-04T09:00:00Z',
        },
      ],
      [`GET /teams/${TEAM_ID}/members`]: [],
    })
    renderWithAuth(<AdminAuditPage />, admin)

    expect(await screen.findByText('Departed Admin removed a member')).toBeInTheDocument()
  })

  it('explains an empty log rather than showing a blank card', async () => {
    mockFetch({
      [`GET /teams/${TEAM_ID}/audit-logs`]: [],
      [`GET /teams/${TEAM_ID}/members`]: [],
    })
    renderWithAuth(<AdminAuditPage />, admin)

    expect(await screen.findByText('Nothing recorded yet')).toBeInTheDocument()
  })
})
