import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { makeAuth } from '../test/factories'
import { mockFetch, renderWithAuth } from '../test/harness'
import type { McpToken } from '../lib/types'
import { SettingsPage } from './SettingsPage'

function token(overrides: Partial<McpToken> = {}): McpToken {
  return {
    id: 'tok-1',
    name: 'Claude',
    prefix: 'lin_abcd12',
    last_used_at: null,
    created_at: '2026-08-15T10:00:00Z',
    ...overrides,
  }
}

describe('settings MCP tokens', () => {
  it('shows a new token once and only lists its prefix afterwards', async () => {
    const fetchMock = mockFetch({
      'GET /me/mcp-tokens': [],
      'POST /me/mcp-tokens': token({
        id: 'tok-2',
        prefix: 'lin_wxyz90',
        token: 'lin_wxyz90secret-value',
      }),
    })
    renderWithAuth(<SettingsPage />, makeAuth())
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /new token/i }))

    expect(await screen.findByText('lin_wxyz90secret-value')).toBeInTheDocument()
    expect(screen.getByText(/cannot be shown again/i)).toBeInTheDocument()
    expect(screen.getByText(/teammates. team-visible goals/i)).toBeInTheDocument()
    expect(screen.getByText(/chatgpt custom connectors/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /copy mcp url/i })).toBeInTheDocument()
    expect(fetchMock.sent('POST /me/mcp-tokens')[0].body).toEqual({ name: 'Claude' })
  })

  it('hides the secret after revoke', async () => {
    const issued = token({ token: 'lin_abcd12secret-value' })
    mockFetch({
      'GET /me/mcp-tokens': [token()],
      'POST /me/mcp-tokens': issued,
      'DELETE /me/mcp-tokens/tok-1': undefined,
    })
    renderWithAuth(<SettingsPage />, makeAuth())
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /new token/i }))
    expect(await screen.findByText('lin_abcd12secret-value')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /revoke lin_abcd12/i }))
    await user.click(screen.getByRole('button', { name: 'Revoke' }))

    expect(screen.queryByText('lin_abcd12secret-value')).not.toBeInTheDocument()
  })
})
