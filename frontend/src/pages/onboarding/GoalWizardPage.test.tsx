import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { GoalWizardPage } from './GoalWizardPage'
import {
  CHALLENGE_ID,
  makeAuth,
  makeChallenge,
  makeGoal,
  makeMyGoals,
} from '../../test/factories'
import { httpError, mockFetch, renderWithAuth } from '../../test/harness'

const auth = makeAuth()

function stub(goals = makeMyGoals([]), extra: Record<string, unknown> = {}) {
  return mockFetch({
    'GET /me/goals': goals,
    'GET /challenges/current': makeChallenge(),
    'GET /auth/me': auth,
    'GET /me/checkins': { days: [] },
    [`GET /challenges/${CHALLENGE_ID}/dashboard`]: { members: [], team_progress: 0 },
    ...extra,
  })
}

describe('goal wizard', () => {
  it('walks all five categories and ends on the review step', async () => {
    stub()
    renderWithAuth(<GoalWizardPage />, auth)
    const user = userEvent.setup()

    await screen.findByText('What does progress look like here?')
    expect(screen.getByText('Prayer, scripture, knowledge, character.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /next area/i }))
    expect(screen.getByText('Strength, weight, endurance, health.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /next area/i }))
    await user.click(screen.getByRole('button', { name: /next area/i }))
    await user.click(screen.getByRole('button', { name: /next area/i }))
    await user.click(screen.getByRole('button', { name: /review commitment/i }))

    expect(screen.getByText("This is what you're committing to.")).toBeInTheDocument()
  })

  it('creates a goal with the step category already applied', async () => {
    const fetchMock = stub(makeMyGoals([]), { 'POST /me/goals': makeGoal() })
    renderWithAuth(<GoalWizardPage />, auth)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /add a goal/i }))
    await user.type(screen.getByLabelText(/goal title/i), 'Read scripture daily')
    await user.click(screen.getByRole('button', { name: 'Add goal' }))

    await waitFor(() => expect(fetchMock.sent('POST /me/goals')).toHaveLength(1))
    expect(fetchMock.sent('POST /me/goals')[0].body).toMatchObject({
      category: 'RELIGIOUS',
      title: 'Read scripture daily',
      tracking_type: 'MILESTONE',
      required: true,
      visibility: 'TEAM',
    })
  })

  it('only asks for numbers when the tracking type needs them', async () => {
    stub()
    renderWithAuth(<GoalWizardPage />, auth)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /add a goal/i }))
    expect(screen.queryByLabelText(/target value/i)).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText(/tracking method/i), 'NUMERIC')
    expect(screen.getByLabelText(/target value/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/starting value/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/direction/i)).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText(/tracking method/i), 'COUNT')
    expect(screen.getByLabelText(/target value/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/starting value/i)).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText(/tracking method/i), 'MANUAL')
    expect(screen.queryByLabelText(/target value/i)).not.toBeInTheDocument()
  })

  it('blocks a numeric goal with no target before it reaches the API', async () => {
    const fetchMock = stub()
    renderWithAuth(<GoalWizardPage />, auth)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /add a goal/i }))
    await user.type(screen.getByLabelText(/goal title/i), 'Deadlift')
    await user.selectOptions(screen.getByLabelText(/tracking method/i), 'NUMERIC')
    await user.click(screen.getByRole('button', { name: 'Add goal' }))

    expect(await screen.findByText('Numeric goals need a target')).toBeInTheDocument()
    expect(fetchMock.sent('POST /me/goals')).toHaveLength(0)
  })

  it('summarises the commitment on the review step', async () => {
    stub(
      makeMyGoals([
        makeGoal({ category: 'RELIGIOUS', title: 'Morning prayer', required: true }),
        makeGoal({ category: 'PHYSICAL', title: 'Deadlift 120kg', required: false }),
        makeGoal({ category: 'PERSONAL', title: 'Something personal', visibility: 'PRIVATE' }),
      ]),
    )
    renderWithAuth(<GoalWizardPage />, auth)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Review' }))
    const summary = screen.getByText('goals total').closest('.review-summary') as HTMLElement
    expect(within(summary).getByText('3')).toBeInTheDocument()
    expect(screen.getByText('Morning prayer')).toBeInTheDocument()
    expect(screen.getByText('Optional')).toBeInTheDocument()
    expect(screen.getByText('Private')).toBeInTheDocument()
  })

  it('requires accepting the terms before the commit button works', async () => {
    stub(makeMyGoals([makeGoal()]))
    renderWithAuth(<GoalWizardPage />, auth)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Review' }))
    const commit = screen.getByRole('button', { name: /committing to this/i })
    expect(commit).toBeDisabled()

    await user.click(screen.getByRole('checkbox'))
    expect(commit).toBeEnabled()
  })

  it('confirms once more before locking the commitment in', async () => {
    const fetchMock = stub(makeMyGoals([makeGoal()]), {
      'POST /me/goals/commit': { locked: true, locked_at: '2026-01-03T00:00:00Z' },
    })
    renderWithAuth(<GoalWizardPage />, auth)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Review' }))
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: /committing to this/i }))

    expect(screen.getByText('Lock in your commitment?')).toBeInTheDocument()
    expect(fetchMock.sent('POST /me/goals/commit')).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: 'Lock it in' }))
    await waitFor(() => expect(fetchMock.sent('POST /me/goals/commit')).toHaveLength(1))
  })

  it('refuses to commit with nothing set', async () => {
    stub()
    renderWithAuth(<GoalWizardPage />, auth)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Review' }))
    expect(screen.getByText("You haven't set any goals")).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /committing to this/i })).not.toBeInTheDocument()
  })

  it('surfaces a server-side lock rather than failing silently', async () => {
    stub(makeMyGoals([makeGoal()]), {
      'POST /me/goals/commit': httpError(409, {
        code: 'GOALS_LOCKED',
        message: 'Your commitment is locked',
      }),
    })
    renderWithAuth(<GoalWizardPage />, auth)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Review' }))
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: /committing to this/i }))
    await user.click(screen.getByRole('button', { name: 'Lock it in' }))

    expect(await screen.findByText('Your commitment is locked')).toBeInTheDocument()
  })

  it('explains tracking methods when the info button is pressed', async () => {
    stub()
    renderWithAuth(<GoalWizardPage />, auth)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /add a goal/i }))
    expect(screen.queryByText(/how you will know you are done/i)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'What do these tracking options mean?' }))
    expect(screen.getByText(/how you will know you are done/i)).toBeInTheDocument()
    expect(screen.getByText(/150 pages of reading/i)).toBeInTheDocument()
  })

  it('explains what a step is from the goal card', async () => {
    stub(
      makeMyGoals([
        makeGoal({ category: 'RELIGIOUS', title: 'Ship LockIn', tracking_type: 'MILESTONE' }),
      ]),
    )
    renderWithAuth(<GoalWizardPage />, auth)
    const user = userEvent.setup()

    await screen.findByText('Ship LockIn')
    expect(screen.queryByText(/named piece of this goal/i)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'What is a step?' }))
    expect(screen.getByText(/named piece of this goal/i)).toBeInTheDocument()
    expect(screen.getByText(/150 pages of reading/i)).toBeInTheDocument()
  })

  it('shows a live countdown to the submission deadline', async () => {
    stub()
    renderWithAuth(<GoalWizardPage />, makeAuth({ goals_due_at: futureDeadline() }))
    expect(await screen.findByText(/until your goals lock/i)).toBeInTheDocument()
  })
})

function futureDeadline(): string {
  return new Date(Date.now() + 3 * 86_400_000).toISOString()
}
