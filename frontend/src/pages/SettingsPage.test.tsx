import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { makeAuth } from '../test/factories'
import { mockFetch, renderWithAuth } from '../test/harness'
import type { McpToken, NotificationPreferences } from '../lib/types'
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

const PUSH_CONFIG = { enabled: true, public_key: 'Bxxxxxxxx' }

const PREFS: NotificationPreferences = {
  muted_types: [],
  types: [
    {
      type: 'MEMBER_CHECKED_IN',
      group: 'Team',
      label: 'Teammate logged progress',
      description: 'Every save.',
    },
    {
      type: 'CHECKIN_DUE',
      group: 'You',
      label: 'You have not checked in today',
      description: 'Evening ping.',
    },
  ],
}

describe('settings MCP tokens', () => {
  it('shows a new token once and only lists its prefix afterwards', async () => {
    const fetchMock = mockFetch({
      'GET /me/mcp-tokens': [],
      'GET /me/push/config': PUSH_CONFIG,
      'GET /me/notification-preferences': PREFS,
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
      'GET /me/push/config': PUSH_CONFIG,
      'GET /me/notification-preferences': PREFS,
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

  it('explains how to install the app and enable push', async () => {
    mockFetch({
      'GET /me/mcp-tokens': [],
      'GET /me/push/config': PUSH_CONFIG,
      'GET /me/notification-preferences': PREFS,
    })
    renderWithAuth(<SettingsPage />, makeAuth())

    expect(await screen.findByRole('heading', { name: /on this device/i })).toBeInTheDocument()
    expect(screen.getByText(/missed check-ins, streaks, pace/i)).toBeInTheDocument()
    expect(screen.getByText(/not available in this browser/i)).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { name: /notification types/i }),
    ).toBeInTheDocument()
  })
})
