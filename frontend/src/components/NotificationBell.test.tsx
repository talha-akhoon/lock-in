import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { NotificationBell } from './NotificationBell'
import { mockFetch, renderRoutes } from '../test/harness'
import type { Notification } from '../lib/types'

function notification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: 'n1',
    type: 'GOALS_DUE_SOON',
    title: 'Your goals are due in 3 days',
    body: 'Define your commitment before the deadline.',
    link_path: '/goals',
    read_at: null,
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

function render() {
  return renderRoutes(
    <>
      <Route path="/" element={<NotificationBell />} />
      <Route path="/goals" element={<h1>My goals</h1>} />
    </>,
    '/',
  )
}

describe('notification bell', () => {
  it('shows the unread count', async () => {
    mockFetch({ 'GET /me/notifications': { unread_count: 3, notifications: [notification()] } })
    render()
    expect(await screen.findByRole('button', { name: 'Notifications, 3 unread' })).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('caps a large count so the badge stays readable', async () => {
    mockFetch({ 'GET /me/notifications': { unread_count: 24, notifications: [] } })
    render()
    await screen.findByRole('button', { name: /24 unread/ })
    expect(screen.getByText('9+')).toBeInTheDocument()
  })

  it('lists notifications when opened', async () => {
    mockFetch({
      'GET /me/notifications': {
        unread_count: 1,
        notifications: [notification(), notification({ id: 'n2', title: 'Yusuf finished a goal', read_at: '2026-01-02T00:00:00Z' })],
      },
    })
    render()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /notifications/i }))
    expect(screen.getByText('Your goals are due in 3 days')).toBeInTheDocument()
    expect(screen.getByText('Yusuf finished a goal')).toBeInTheDocument()
    expect(screen.getByText('1 unread')).toBeInTheDocument()
  })

  it('marks one read and follows its link', async () => {
    const fetchMock = mockFetch({
      'GET /me/notifications': { unread_count: 1, notifications: [notification()] },
      'POST /me/notifications/n1/read': { id: 'n1', read: true },
    })
    render()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /notifications/i }))
    await user.click(screen.getByRole('button', { name: /your goals are due/i }))

    await waitFor(() => expect(fetchMock.sent('POST /me/notifications/n1/read')).toHaveLength(1))
    expect(screen.getByRole('heading', { name: 'My goals' })).toBeInTheDocument()
  })

  it('does not re-mark something already read', async () => {
    const fetchMock = mockFetch({
      'GET /me/notifications': {
        unread_count: 0,
        notifications: [notification({ read_at: '2026-01-02T00:00:00Z' })],
      },
    })
    render()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Notifications' }))
    await user.click(screen.getByRole('button', { name: /your goals are due/i }))
    expect(fetchMock.sent('POST /me/notifications/n1/read')).toHaveLength(0)
  })

  it('marks everything read in one go', async () => {
    const fetchMock = mockFetch({
      'GET /me/notifications': { unread_count: 2, notifications: [notification()] },
      'POST /me/notifications/read-all': { marked: 2 },
    })
    render()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /notifications/i }))
    await user.click(screen.getByRole('button', { name: /mark all read/i }))
    await waitFor(() => expect(fetchMock.sent('POST /me/notifications/read-all')).toHaveLength(1))
  })

  it('says so when there is nothing waiting', async () => {
    mockFetch({ 'GET /me/notifications': { unread_count: 0, notifications: [] } })
    render()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Notifications' }))
    expect(screen.getByText('All caught up')).toBeInTheDocument()
    expect(screen.getByText(/Deadlines, check-ins and teammate wins land here/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /mark all read/i })).not.toBeInTheDocument()
  })
})
