import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { InfoTip } from './InfoTip'

describe('InfoTip', () => {
  it('hides the explanation until the button is pressed', async () => {
    const user = userEvent.setup()
    render(
      <InfoTip label="What do these tracking options mean?">
        <p>A running total adds what you did today.</p>
      </InfoTip>,
    )

    expect(screen.queryByText(/running total/i)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'What do these tracking options mean?' }))
    expect(screen.getByText(/running total/i)).toBeInTheDocument()
  })

  it('closes on a second click and on Escape', async () => {
    const user = userEvent.setup()
    render(
      <InfoTip label="What is a step?">
        <p>A step is a named piece of this goal.</p>
      </InfoTip>,
    )

    const button = screen.getByRole('button', { name: 'What is a step?' })
    await user.click(button)
    expect(screen.getByText(/named piece/i)).toBeInTheDocument()

    await user.click(button)
    expect(screen.queryByText(/named piece/i)).not.toBeInTheDocument()

    await user.click(button)
    await user.keyboard('{Escape}')
    expect(screen.queryByText(/named piece/i)).not.toBeInTheDocument()
  })
})
