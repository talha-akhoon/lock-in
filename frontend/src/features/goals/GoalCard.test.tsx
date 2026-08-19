import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { GoalCard } from './GoalCard'
import { makeGoal } from '../../test/factories'
import { mockFetch, renderWithProviders } from '../../test/harness'

function renderCard(props: Partial<Parameters<typeof GoalCard>[0]>) {
  return render(
    <MemoryRouter>
      <GoalCard goal={makeGoal({ title: 'Land 2 interviews' })} {...props} />
    </MemoryRouter>,
  )
}

function twoSteps() {
  const first = makeGoal({ title: 'Finish the API' })
  const second = makeGoal({ title: 'Finish the UI' })
  return makeGoal({ title: 'Ship the app', children: [first, second] })
}

describe('GoalCard add-step gating', () => {
  it('offers Add step when adding is allowed even if the goal is locked', () => {
    renderCard({ editable: false, canAddChild: true, onAddChild: () => {}, onDelete: () => {} })

    expect(screen.getByRole('button', { name: /add step/i })).toBeInTheDocument()
    // Locked: no delete, so the step is an addition that cannot then be removed.
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument()
  })

  it('hides Add step once adding is closed (challenge over)', () => {
    renderCard({ editable: false, canAddChild: false, onAddChild: () => {} })

    expect(screen.queryByRole('button', { name: /add step/i })).not.toBeInTheDocument()
  })
})

describe('GoalCard step reorder', () => {
  it('offers move buttons when there are two or more steps', () => {
    renderWithProviders(<GoalCard goal={twoSteps()} />)

    expect(screen.getByRole('button', { name: /move finish the api down/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /move finish the api up/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /move finish the ui down/i })).toBeDisabled()
  })

  it('hides move buttons when there is only one step', () => {
    const parent = makeGoal({
      title: 'Ship the app',
      children: [makeGoal({ title: 'Finish the API' })],
    })
    renderWithProviders(<GoalCard goal={parent} />)

    expect(screen.queryByRole('button', { name: /move /i })).not.toBeInTheDocument()
  })

  it('sends the swapped ids when a step is moved down', async () => {
    const parent = twoSteps()
    const fetchMock = mockFetch({
      [`PATCH /goals/${parent.id}/children/order`]: parent,
    })
    renderWithProviders(<GoalCard goal={parent} />)

    await userEvent.click(screen.getByRole('button', { name: /move finish the api down/i }))

    await waitFor(() =>
      expect(fetchMock.sent(`PATCH /goals/${parent.id}/children/order`)).toHaveLength(1),
    )
    expect(fetchMock.sent(`PATCH /goals/${parent.id}/children/order`)[0].body).toEqual({
      ordered_ids: [parent.children[1].id, parent.children[0].id],
    })
  })

  it('still offers reorder when the goal is locked', () => {
    renderWithProviders(
      <GoalCard goal={twoSteps()} editable={false} canAddChild onAddChild={() => {}} />,
    )

    expect(screen.getByRole('button', { name: /move finish the api down/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument()
  })
})
