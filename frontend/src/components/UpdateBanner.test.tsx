import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { UpdateBanner } from './UpdateBanner'

afterEach(() => {
  vi.unstubAllGlobals()
})

function stubVersion(body: unknown, status = 200) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
}

describe('UpdateBanner', () => {
  it('asks the user to refresh when version.json does not match', async () => {
    stubVersion({ version: 'new' })
    render(<UpdateBanner runningVersion="old" />)
    expect(await screen.findByRole('button', { name: 'Refresh' })).toBeInTheDocument()
    expect(screen.getByText('A new version of LockIn is ready')).toBeInTheDocument()
  })

  it('stays hidden when the running build already matches', async () => {
    stubVersion({ version: 'abc' })
    render(<UpdateBanner runningVersion="abc" />)
    await waitFor(() => {
      expect(fetch).toHaveBeenCalled()
    })
    expect(screen.queryByRole('button', { name: 'Refresh' })).not.toBeInTheDocument()
  })

  it('stays hidden when the version check fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new Error('offline'))))
    render(<UpdateBanner runningVersion="old" />)
    await waitFor(() => {
      expect(fetch).toHaveBeenCalled()
    })
    expect(screen.queryByRole('button', { name: 'Refresh' })).not.toBeInTheDocument()
  })

  it('reloads the page when the user chooses Refresh', async () => {
    stubVersion({ version: 'new' })
    const reload = vi.fn()
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...window.location, reload },
    })
    render(<UpdateBanner runningVersion="old" />)
    await userEvent.click(await screen.findByRole('button', { name: 'Refresh' }))
    expect(reload).toHaveBeenCalled()
  })
})
