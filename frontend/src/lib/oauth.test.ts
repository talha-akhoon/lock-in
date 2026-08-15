import { describe, expect, it } from 'vitest'
import { safeOAuthNext } from './oauth'

describe('safeOAuthNext', () => {
  it('allows only the authorize path, including a ChatGPT redirect in the query', () => {
    const next =
      '/oauth/authorize?client_id=https://chatgpt.com/client&redirect_uri=https://chatgpt.com/connector/oauth/cb'
    expect(safeOAuthNext(next)).toBe(next)
  })

  it('rejects open redirects and other app paths', () => {
    expect(safeOAuthNext('/dashboard')).toBeNull()
    expect(safeOAuthNext('//evil.example/oauth/authorize')).toBeNull()
    expect(safeOAuthNext('/oauth/authorize/../login')).toBeNull()
    expect(safeOAuthNext(null)).toBeNull()
  })
})
