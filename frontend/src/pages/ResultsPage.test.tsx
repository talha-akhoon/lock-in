import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ResultsPage } from './ResultsPage'
import { CHALLENGE_ID, OTHER_ID, USER_ID, makeAuth, makeChallenge } from '../test/factories'
import { httpError, mockFetch, renderWithAuth } from '../test/harness'
import type { ForfeitLine, Outcome } from '../lib/types'

function outcome(overrides: Partial<Outcome> = {}): Outcome {
  return {
    participant_id: 'p1',
    user_id: USER_ID,
    display_name: 'Sam Ali',
    avatar_url: null,
    required_goals_total: 4,
    required_goals_completed: 4,
    optional_goals_total: 2,
    optional_goals_completed: 1,
    final_progress_percentage: 88,
    succeeded: true,
    total_forfeit_pence: 0,
    ...overrides,
  }
}

function forfeit(overrides: Partial<ForfeitLine> = {}): ForfeitLine {
  return {
    id: 'f1',
    from_user_id: OTHER_ID,
    from_display_name: 'Yusuf Khan',
    to_user_id: USER_ID,
    to_display_name: 'Sam Ali',
    amount_pence: 25000,
    status: 'OUTSTANDING',
    settled_at: null,
    ...overrides,
  }
}

function stub(outcomes: Outcome[], forfeits: ForfeitLine[]) {
  mockFetch({
    'GET /challenges/current': makeChallenge({ status: 'COMPLETED', days_remaining: 0 }),
    [`GET /challenges/${CHALLENGE_ID}/outcomes`]: {
      challenge: makeChallenge({ status: 'COMPLETED' }),
      outcomes,
      forfeits,
    },
  })
}

const auth = makeAuth({ challenge_status: 'COMPLETED' })

describe('challenge outcomes', () => {
  it('congratulates someone who finished and itemises what they are owed', async () => {
    stub(
      [outcome(), outcome({ participant_id: 'p2', user_id: OTHER_ID, display_name: 'Yusuf Khan', succeeded: false, required_goals_completed: 2, total_forfeit_pence: 25000 })],
      [forfeit()],
    )
    renderWithAuth(<ResultsPage />, auth)

    expect(await screen.findByText('You did what you said you would.')).toBeInTheDocument()
    expect(screen.getByText(/You are owed £250/)).toBeInTheDocument()
    expect(screen.getByText('You receive £250')).toBeInTheDocument()
    expect(screen.getByText('Outstanding')).toBeInTheDocument()
  })

  it('tells someone who fell short exactly who they owe', async () => {
    stub(
      [
        outcome({ succeeded: false, required_goals_completed: 1, final_progress_percentage: 34, total_forfeit_pence: 50000 }),
        outcome({ participant_id: 'p2', user_id: OTHER_ID, display_name: 'Yusuf Khan' }),
      ],
      [
        forfeit({ from_user_id: USER_ID, from_display_name: 'Sam Ali', to_user_id: OTHER_ID, to_display_name: 'Yusuf Khan' }),
        forfeit({ id: 'f2', from_user_id: USER_ID, from_display_name: 'Sam Ali', to_user_id: 'third', to_display_name: 'Aisha Noor' }),
      ],
    )
    renderWithAuth(<ResultsPage />, auth)

    expect(await screen.findByText('You fell short.')).toBeInTheDocument()
    expect(screen.getByText(/You owe £500 in total/)).toBeInTheDocument()
    expect(screen.getByText('You pay £500')).toBeInTheDocument()
    expect(screen.getByText('Aisha Noor')).toBeInTheDocument()
  })

  it('celebrates a clean sweep with no forfeits', async () => {
    stub([outcome()], [])
    renderWithAuth(<ResultsPage />, auth)

    expect(await screen.findByText('No forfeits')).toBeInTheDocument()
    expect(screen.getByText(/Nobody owes you anything/)).toBeInTheDocument()
  })

  it('withholds results until the challenge has actually finished', async () => {
    mockFetch({
      'GET /challenges/current': makeChallenge({ days_remaining: 40 }),
      [`GET /challenges/${CHALLENGE_ID}/outcomes`]: httpError(
        409,
        'This challenge has not finished yet',
      ),
    })
    renderWithAuth(<ResultsPage />, makeAuth())

    expect(await screen.findByText('Not finished yet')).toBeInTheDocument()
    expect(screen.getByText(/40 days to go/)).toBeInTheDocument()
  })
})
