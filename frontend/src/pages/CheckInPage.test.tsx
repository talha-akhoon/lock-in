import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { CheckInPage } from './CheckInPage'
import { makeAuth, makeGoal, makeHeatmap } from '../test/factories'
import { mockFetch, renderWithAuth } from '../test/harness'
import { isoToday } from '../lib/format'
import type { Goal } from '../lib/types'

const today = isoToday()

function stub(goals: Goal[], extra: Record<string, unknown> = {}) {
  return mockFetch({
    [`GET /me/checkins/${today}`]: { date: today, note: null, exists: false, goals },
    'GET /me/checkins': makeHeatmap({ today, streak: 4, total_days_logged: 9 }),
    'POST /me/checkins': { id: 'checkin-1', date: today, note: null, updates: 1 },
    ...extra,
  })
}

describe('check-in form', () => {
  it('builds one update per tracking type from what was typed', async () => {
    const numeric = makeGoal({
      title: 'Bodyweight',
      tracking_type: 'NUMERIC',
      current_value: 84,
      target_value: 78,
      target_direction: 'AT_MOST',
      unit: 'kg',
    })
    const count = makeGoal({ title: 'Gym sessions', tracking_type: 'COUNT', target_value: 100 })
    const manual = makeGoal({
      title: 'Business plan',
      tracking_type: 'MANUAL',
      manual_progress_percentage: 20,
    })
    const milestone = makeGoal({ title: 'Read Sahih Bukhari', tracking_type: 'MILESTONE' })
    const fetchMock = stub([numeric, count, manual, milestone])

    renderWithAuth(<CheckInPage />, makeAuth())
    const user = userEvent.setup()

    await user.clear(await screen.findByLabelText('Bodyweight (kg)'))
    await user.type(screen.getByLabelText('Bodyweight (kg)'), '82')
    await user.type(screen.getByLabelText('Gym sessions'), '2')
    await user.clear(screen.getByLabelText('Business plan'))
    await user.type(screen.getByLabelText('Business plan'), '35')
    await user.click(screen.getByLabelText('Read Sahih Bukhari'))
    await user.type(screen.getByLabelText(/notes/i), 'Heavy day')
    await user.click(screen.getByRole('button', { name: /save today/i }))

    await waitFor(() => expect(fetchMock.sent('POST /me/checkins')).toHaveLength(1))
    expect(fetchMock.sent('POST /me/checkins')[0].body).toEqual({
      date: today,
      note: 'Heavy day',
      updates: [
        { goal_id: numeric.id, numeric_value: 82 },
        { goal_id: count.id, numeric_delta: 2 },
        { goal_id: manual.id, manual_percentage: 35 },
        { goal_id: milestone.id, completed: true },
      ],
    })
  })

  it('sends nothing for goals left untouched', async () => {
    const numeric = makeGoal({
      title: 'Bodyweight',
      tracking_type: 'NUMERIC',
      current_value: 84,
      target_value: 78,
    })
    const count = makeGoal({ title: 'Gym sessions', tracking_type: 'COUNT', target_value: 100 })
    const fetchMock = stub([numeric, count])

    renderWithAuth(<CheckInPage />, makeAuth())
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText(/notes/i), 'Rest day')
    await user.click(screen.getByRole('button', { name: /save today/i }))

    await waitFor(() => expect(fetchMock.sent('POST /me/checkins')).toHaveLength(1))
    expect(fetchMock.sent('POST /me/checkins')[0].body).toEqual({
      date: today,
      note: 'Rest day',
      updates: [],
    })
  })

  it('refuses an entirely empty submission', async () => {
    const fetchMock = stub([makeGoal({ title: 'Gym sessions', tracking_type: 'COUNT', target_value: 10 })])
    renderWithAuth(<CheckInPage />, makeAuth())
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /save today/i }))
    expect(
      screen.getByText('Nothing to save yet — update a goal or leave a note.'),
    ).toBeInTheDocument()
    expect(fetchMock.sent('POST /me/checkins')).toHaveLength(0)
  })

  it('offers sub-goals rather than the parent the API rejects', async () => {
    const child = makeGoal({
      title: 'Chapter one',
      tracking_type: 'MILESTONE',
      parent_goal_id: 'parent',
    })
    const parent = makeGoal({ id: 'parent', title: 'Finish the book', children: [child] })
    stub([parent])

    renderWithAuth(<CheckInPage />, makeAuth())
    expect(await screen.findByLabelText('Chapter one')).toBeInTheDocument()
    expect(screen.queryByLabelText('Finish the book')).not.toBeInTheDocument()
    expect(screen.getByText('Finish the book')).toBeInTheDocument()
  })

  it('prefills an existing day and says it will be updated', async () => {
    const numeric = makeGoal({
      title: 'Bodyweight',
      tracking_type: 'NUMERIC',
      current_value: 84,
      target_value: 78,
    })
    mockFetch({
      [`GET /me/checkins/${today}`]: {
        date: today,
        note: 'Already logged',
        exists: true,
        goals: [numeric],
      },
      'GET /me/checkins': makeHeatmap({ today }),
    })

    renderWithAuth(<CheckInPage />, makeAuth())
    expect(await screen.findByDisplayValue('Already logged')).toBeInTheDocument()
    expect(screen.getByDisplayValue('84')).toBeInTheDocument()
    expect(screen.getByText(/saving again updates it/i)).toBeInTheDocument()
  })

  it('shows the streak from the API', async () => {
    stub([makeGoal({ tracking_type: 'MILESTONE' })])
    renderWithAuth(<CheckInPage />, makeAuth())
    expect(await screen.findByText('4 day streak')).toBeInTheDocument()
    expect(screen.getByText('9 days logged in total')).toBeInTheDocument()
  })

  it('points a member with no goals at the wizard', async () => {
    stub([])
    renderWithAuth(<CheckInPage />, makeAuth())
    expect(await screen.findByText('No goals to check in against')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /set my goals/i })).toBeInTheDocument()
  })
})
