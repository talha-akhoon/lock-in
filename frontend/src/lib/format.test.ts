import { describe, expect, it } from 'vitest'
import {
  formatPence,
  formatRemaining,
  goalValueLabel,
  isoToday,
  relativeTime,
  timeRemaining,
} from './format'

describe('money', () => {
  it('renders whole pounds without decimals', () => {
    expect(formatPence(20000)).toBe('£200')
    expect(formatPence(0)).toBe('£0')
  })

  it('keeps pence when they matter', () => {
    expect(formatPence(20050)).toBe('£200.50')
  })
})

describe('countdown', () => {
  const now = new Date('2026-01-01T12:00:00Z')

  it('breaks the gap into days, hours and minutes', () => {
    expect(timeRemaining('2026-01-03T15:30:45Z', now)).toEqual({
      days: 2,
      hours: 3,
      minutes: 30,
      seconds: 45,
      expired: false,
    })
  })

  it('reports an elapsed deadline as expired', () => {
    expect(timeRemaining('2025-12-31T12:00:00Z', now).expired).toBe(true)
  })

  it('drops days once inside the final day and seconds once past a day', () => {
    expect(formatRemaining(timeRemaining('2026-01-03T15:30:45Z', now))).toBe('2d 3h 30m')
    expect(formatRemaining(timeRemaining('2026-01-01T14:30:45Z', now))).toBe('2h 30m 45s')
    expect(formatRemaining(timeRemaining('2026-01-01T12:04:30Z', now))).toBe('4m 30s')
  })

  it('says Locked once the deadline has gone', () => {
    expect(formatRemaining(timeRemaining('2025-01-01T00:00:00Z', now))).toBe('Locked')
  })
})

describe('relative time', () => {
  const now = new Date('2026-01-10T12:00:00Z')

  it('describes recent moments in words', () => {
    expect(relativeTime('2026-01-10T11:59:30Z', now)).toBe('just now')
    expect(relativeTime('2026-01-10T11:30:00Z', now)).toBe('30m ago')
    expect(relativeTime('2026-01-10T09:00:00Z', now)).toBe('3h ago')
    expect(relativeTime('2026-01-08T12:00:00Z', now)).toBe('2d ago')
  })

  it('falls back to a date beyond a week', () => {
    expect(relativeTime('2025-12-01T12:00:00Z', now)).toContain('2025')
  })
})

describe('isoToday', () => {
  it('uses the local calendar day, not the UTC one', () => {
    // 23:30 on the 5th in a UTC+2 zone is still the 5th locally.
    const local = new Date(2026, 0, 5, 23, 30)
    expect(isoToday(local)).toBe('2026-01-05')
  })
})

describe('goal value labels', () => {
  const base = {
    current_value: null,
    baseline_value: null,
    target_value: null,
    manual_progress_percentage: null,
    completed_at: null,
    unit: null,
  }

  it('describes a milestone by completion', () => {
    expect(goalValueLabel({ ...base, tracking_type: 'MILESTONE' })).toBe('Not yet complete')
    expect(
      goalValueLabel({ ...base, tracking_type: 'MILESTONE', completed_at: '2026-01-01' }),
    ).toBe('Complete')
  })

  it('describes a numeric goal against its target', () => {
    expect(
      goalValueLabel({
        ...base,
        tracking_type: 'NUMERIC',
        current_value: '95.0000',
        target_value: '120.0000',
        unit: 'kg',
      }),
    ).toBe('95 / 120 kg')
  })

  it('keeps a fractional figure without the API padding', () => {
    expect(
      goalValueLabel({
        ...base,
        tracking_type: 'NUMERIC',
        current_value: '72.5000',
        target_value: '100.0000',
        unit: 'kg',
      }),
    ).toBe('72.5 / 100 kg')
  })

  it('falls back to the baseline before any update', () => {
    expect(
      goalValueLabel({
        ...base,
        tracking_type: 'NUMERIC',
        baseline_value: '80.0000',
        target_value: '120.0000',
      }),
    ).toBe('80 / 120')
  })

  it('describes a manual goal as a percentage', () => {
    expect(
      goalValueLabel({ ...base, tracking_type: 'MANUAL', manual_progress_percentage: 40 }),
    ).toBe('40% done')
  })
})
