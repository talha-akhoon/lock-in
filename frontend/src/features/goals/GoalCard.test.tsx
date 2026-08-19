import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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

function stubRect(node: Element, top: number, height = 40) {
  Object.defineProperty(node, 'getBoundingClientRect', {
    configurable: true,
    value: () => ({
      x: 0,
      y: top,
      top,
      bottom: top + height,
      left: 0,
      right: 200,
      width: 200,
      height,
      toJSON: () => ({}),
    }),
  })
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
  it('offers a drag handle when there are two or more steps', () => {
    renderWithProviders(<GoalCard goal={twoSteps()} />)

    expect(screen.getByRole('button', { name: /reorder finish the api/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reorder finish the ui/i })).toBeInTheDocument()
  })

  it('hides the drag handle when there is only one step', () => {
    const parent = makeGoal({
      title: 'Ship the app',
      children: [makeGoal({ title: 'Finish the API' })],
    })
    renderWithProviders(<GoalCard goal={parent} />)

    expect(screen.queryByRole('button', { name: /reorder /i })).not.toBeInTheDocument()
  })

  it('sends the swapped ids when a step is dragged past its neighbour', async () => {
    const parent = twoSteps()
    const fetchMock = mockFetch({
      [`PATCH /goals/${parent.id}/children/order`]: parent,
    })
    renderWithProviders(<GoalCard goal={parent} />)

    const handle = screen.getByRole('button', { name: /reorder finish the api/i })
    const firstRow = handle.closest('.subgoal')
    const secondRow = screen.getByRole('button', { name: /reorder finish the ui/i }).closest('.subgoal')
    expect(firstRow).toBeTruthy()
    expect(secondRow).toBeTruthy()
    stubRect(firstRow!, 0)
    stubRect(secondRow!, 40)

    fireEvent.pointerDown(handle, { pointerId: 1, clientY: 20, button: 0 })
    fireEvent.pointerMove(window, { pointerId: 1, clientY: 70 })
    fireEvent.pointerUp(window, { pointerId: 1, clientY: 70 })

    await waitFor(() =>
      expect(fetchMock.sent(`PATCH /goals/${parent.id}/children/order`)).toHaveLength(1),
    )
    expect(fetchMock.sent(`PATCH /goals/${parent.id}/children/order`)[0].body).toEqual({
      ordered_ids: [parent.children[1].id, parent.children[0].id],
    })
  })

  it('sends the swapped ids when a step is moved with the arrow keys', async () => {
    const parent = twoSteps()
    const fetchMock = mockFetch({
      [`PATCH /goals/${parent.id}/children/order`]: parent,
    })
    renderWithProviders(<GoalCard goal={parent} />)

    screen.getByRole('button', { name: /reorder finish the api/i }).focus()
    await userEvent.keyboard('{ArrowDown}')

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

    expect(screen.getByRole('button', { name: /reorder finish the api/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument()
  })
})
