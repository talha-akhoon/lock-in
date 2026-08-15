import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { StartPage } from './StartPage'
import { TEAM_ID, makeAuth } from '../../test/factories'
import { httpError, mockFetch, renderWithAuth } from '../../test/harness'

const fresh = makeAuth({ team: null, role: null, challenge_id: null, participant_id: null })

describe('bootstrap', () => {
  it('offers both ways in, so a first user is never stranded', async () => {
    mockFetch({})
    renderWithAuth(<StartPage />, fresh)

    expect(screen.getByRole('button', { name: /start a team/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /join with a code/i })).toBeInTheDocument()
  })

  it('creates a team and moves on to the challenge', async () => {
    const fetchMock = mockFetch({ 'POST /teams': { id: TEAM_ID, name: 'The Sunday Circle' } })
    renderWithAuth(<StartPage />, fresh)
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /start a team/i }))
    await user.type(screen.getByLabelText(/team name/i), 'The Sunday Circle')
    await user.click(screen.getByRole('button', { name: /create team/i }))

    await waitFor(() => expect(fetchMock.sent('POST /teams')).toHaveLength(1))
    expect(fetchMock.sent('POST /teams')[0].body).toEqual({ name: 'The Sunday Circle' })
  })

  it('rejects a one-character team name before calling the API', async () => {
    const fetchMock = mockFetch({})
    renderWithAuth(<StartPage />, fresh)
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /start a team/i }))
    await user.type(screen.getByLabelText(/team name/i), 'A')
    await user.click(screen.getByRole('button', { name: /create team/i }))

    expect(await screen.findByText(/at least 2 characters/i)).toBeInTheDocument()
    expect(fetchMock.sent('POST /teams')).toHaveLength(0)
  })

  it('redeems an invitation code, upper-casing it on the way', async () => {
    const fetchMock = mockFetch({ 'POST /invitations/redeem': { team_id: TEAM_ID } })
    renderWithAuth(<StartPage />, fresh)
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /join with a code/i }))
    await user.type(screen.getByLabelText(/invitation code/i), 'abcd-efgh')
    await user.click(screen.getByRole('button', { name: /join team/i }))

    await waitFor(() => expect(fetchMock.sent('POST /invitations/redeem')).toHaveLength(1))
    expect(fetchMock.sent('POST /invitations/redeem')[0].body).toEqual({ code: 'ABCD-EFGH' })
  })

  it('rejects a malformed code locally', async () => {
    const fetchMock = mockFetch({})
    renderWithAuth(<StartPage />, fresh)
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /join with a code/i }))
    await user.type(screen.getByLabelText(/invitation code/i), 'NOPE')
    await user.click(screen.getByRole('button', { name: /join team/i }))

    expect(await screen.findByText('Codes look like ABCD-EFGH')).toBeInTheDocument()
    expect(fetchMock.sent('POST /invitations/redeem')).toHaveLength(0)
  })

  it('surfaces a rejected code from the server', async () => {
    mockFetch({ 'POST /invitations/redeem': httpError(404, 'Invitation not found') })
    renderWithAuth(<StartPage />, fresh)
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /join with a code/i }))
    await user.type(screen.getByLabelText(/invitation code/i), 'ABCD-EFGH')
    await user.click(screen.getByRole('button', { name: /join team/i }))

    expect(await screen.findByText('Invitation not found')).toBeInTheDocument()
  })
})
