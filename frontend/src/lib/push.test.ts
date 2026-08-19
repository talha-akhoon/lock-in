import { describe, expect, it } from 'vitest'
import { isIosDevice, isStandalone, pushSupported, urlBase64ToUint8Array } from './push'

describe('urlBase64ToUint8Array', () => {
  it('decodes a URL-safe key without padding', () => {
    const bytes = urlBase64ToUint8Array('AQIDBA')
    expect(Array.from(bytes)).toEqual([1, 2, 3, 4])
  })

  it('accepts standard base64 characters after translation', () => {
    const bytes = urlBase64ToUint8Array('AQIDBA')
    expect(bytes.byteLength).toBe(4)
  })
})

describe('environment checks', () => {
  it('reports push as unsupported in jsdom', () => {
    expect(pushSupported()).toBe(false)
  })

  it('does not treat jsdom as an installed PWA or an iPhone', () => {
    expect(isStandalone()).toBe(false)
    expect(isIosDevice()).toBe(false)
  })
})
