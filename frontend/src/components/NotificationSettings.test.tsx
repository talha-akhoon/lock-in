import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { NotificationPreferences } from '../lib/types'
import { mockFetch, renderWithProviders } from '../test/harness'
import { NotificationSettings } from './NotificationSettings'

const PREFS: NotificationPreferences = {
  muted_types: [],
  types: [
    {
      type: 'MEMBER_CHECKED_IN',
      group: 'Team',
      label: 'Teammate logged progress',
      description: 'Every save — another LC problem, another session.',
    },
    {
      type: 'CHECKIN_DUE',
      group: 'You',
      label: 'You have not checked in today',
      description: 'Evening ping in the challenge timezone.',
    },
  ],
}

describe('notification mute settings', () => {
  it('mutes a type when the checkbox is cleared', async () => {
    const fetchMock = mockFetch({
      'GET /me/notification-preferences': PREFS,
      'PUT /me/notification-preferences': {
        ...PREFS,
        muted_types: ['CHECKIN_DUE'],
      },
    })
    renderWithProviders(<NotificationSettings />)
    const user = userEvent.setup()

    const box = await screen.findByRole('checkbox', { name: /you have not checked in today/i })
    expect(box).toBeChecked()
    await user.click(box)

    await waitFor(() =>
      expect(fetchMock.sent('PUT /me/notification-preferences')[0].body).toEqual({
        muted_types: ['CHECKIN_DUE'],
      }),
    )
  })
})
