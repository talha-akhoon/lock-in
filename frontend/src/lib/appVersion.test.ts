import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchRemoteVersion, isStaleVersion, shouldPromptRefresh } from './appVersion'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('isStaleVersion', () => {
  it('prompts when the origin reports a different build', () => {
    expect(isStaleVersion('old', { version: 'new' })).toBe(true)
  })

  it('stays quiet when the running build already matches', () => {
    expect(isStaleVersion('abc', { version: 'abc' })).toBe(false)
  })

  it('ignores a missing or empty version payload', () => {
    expect(isStaleVersion('abc', null)).toBe(false)
    expect(isStaleVersion('abc', {})).toBe(false)
    expect(isStaleVersion('abc', { version: '' })).toBe(false)
    expect(isStaleVersion('abc', { version: 12 })).toBe(false)
  })
})

describe('shouldPromptRefresh', () => {
  it('asks the origin for version.json without using the HTTP cache', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ version: 'same' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    await fetchRemoteVersion()
    expect(fetchMock).toHaveBeenCalledWith('/version.json', { cache: 'no-store' })
  })

  it('prompts when version.json does not match the running build', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ version: 'new' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    expect(await shouldPromptRefresh('old')).toBe(true)
  })

  it('stays quiet when the running build already matches', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ version: 'abc' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    expect(await shouldPromptRefresh('abc')).toBe(false)
  })

  it('stays quiet when the version check fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new Error('offline'))))
    expect(await shouldPromptRefresh('old')).toBe(false)
  })
})
