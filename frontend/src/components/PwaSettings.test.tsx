import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PwaSettings } from './PwaSettings'
import { mockFetch, renderWithProviders } from '../test/harness'

const push = vi.hoisted(() => ({
  pushSupported: vi.fn(() => true),
  isStandalone: vi.fn(() => false),
  isIosDevice: vi.fn(() => false),
  hasPushSubscription: vi.fn(async () => false),
  enablePush: vi.fn(async () => undefined),
  disablePush: vi.fn(async () => undefined),
}))

vi.mock('../lib/push', () => push)

describe('PWA settings', () => {
  beforeEach(() => {
    push.pushSupported.mockReturnValue(true)
    push.isStandalone.mockReturnValue(false)
    push.isIosDevice.mockReturnValue(false)
    push.hasPushSubscription.mockResolvedValue(false)
    push.enablePush.mockResolvedValue(undefined)
    push.disablePush.mockResolvedValue(undefined)
  })

  it('turns push on against the current VAPID key', async () => {
    mockFetch({ 'GET /me/push/config': { enabled: true, public_key: 'Bpublic' } })
    renderWithProviders(<PwaSettings />)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /turn on/i }))

    await waitFor(() => expect(push.enablePush).toHaveBeenCalledWith('Bpublic'))
    expect(await screen.findByRole('button', { name: /turn off/i })).toBeInTheDocument()
  })

  it('turns push off', async () => {
    push.hasPushSubscription.mockResolvedValue(true)
    mockFetch({ 'GET /me/push/config': { enabled: true, public_key: 'Bpublic' } })
    renderWithProviders(<PwaSettings />)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /turn off/i }))
    await waitFor(() => expect(push.disablePush).toHaveBeenCalled())
    expect(await screen.findByRole('button', { name: /turn on/i })).toBeInTheDocument()
  })

  it('shows an install button when the browser offers one', async () => {
    mockFetch({ 'GET /me/push/config': { enabled: true, public_key: 'Bpublic' } })
    renderWithProviders(<PwaSettings />)

    const prompt = vi.fn(async () => undefined)
    const event = new Event('beforeinstallprompt', { cancelable: true }) as Event & {
      prompt: typeof prompt
      userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
    }
    event.preventDefault = vi.fn()
    event.prompt = prompt
    event.userChoice = Promise.resolve({ outcome: 'accepted' })
    window.dispatchEvent(event)

    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /install lockin/i }))
    expect(prompt).toHaveBeenCalled()
    expect(await screen.findByText('Installed')).toBeInTheDocument()
  })
})
