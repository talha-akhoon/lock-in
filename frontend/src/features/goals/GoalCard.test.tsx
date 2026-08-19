import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { GoalCard } from './GoalCard'
import { makeGoal } from '../../test/factories'

function renderCard(props: Partial<Parameters<typeof GoalCard>[0]>) {
  return render(
    <MemoryRouter>
      <GoalCard goal={makeGoal({ title: 'Land 2 interviews' })} {...props} />
    </MemoryRouter>,
  )
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
