import { describe, expect, it } from 'vitest'
import { makeGoal } from '../../test/factories'
import { buildCheckinPayload, buildCheckinUpdates, checkinTargets } from './payload'

describe('check-in payload', () => {
  it('sends a numeric goal as an absolute value', () => {
    const goal = makeGoal({ tracking_type: 'NUMERIC', current_value: 80, target_value: 120 })
    expect(buildCheckinUpdates([goal], { [goal.id]: '95' })).toEqual([
      { goal_id: goal.id, numeric_value: 95 },
    ])
  })

  it('sends a count goal as a delta so daily totals accumulate', () => {
    const goal = makeGoal({ tracking_type: 'COUNT', current_value: 12, target_value: 100 })
    expect(buildCheckinUpdates([goal], { [goal.id]: '3' })).toEqual([
      { goal_id: goal.id, numeric_delta: 3 },
    ])
  })

  it('sends a count goal as an absolute value before kick-off', () => {
    const goal = makeGoal({ tracking_type: 'COUNT', current_value: 0, target_value: 100 })
    expect(buildCheckinUpdates([goal], { [goal.id]: '2' }, true)).toEqual([
      { goal_id: goal.id, numeric_value: 2 },
    ])
  })

  it('sends a manual goal as a percentage', () => {
    const goal = makeGoal({ tracking_type: 'MANUAL', manual_progress_percentage: 20 })
    expect(buildCheckinUpdates([goal], { [goal.id]: '45' })).toEqual([
      { goal_id: goal.id, manual_percentage: 45 },
    ])
  })

  it('clamps a manual percentage into range', () => {
    const goal = makeGoal({ tracking_type: 'MANUAL', manual_progress_percentage: 0 })
    expect(buildCheckinUpdates([goal], { [goal.id]: '140' })).toEqual([
      { goal_id: goal.id, manual_percentage: 100 },
    ])
  })

  it('sends a milestone as a completion flag', () => {
    const goal = makeGoal({ tracking_type: 'MILESTONE' })
    expect(buildCheckinUpdates([goal], { [goal.id]: true })).toEqual([
      { goal_id: goal.id, completed: true },
    ])
  })

  it('can reopen a milestone that was completed', () => {
    const goal = makeGoal({ tracking_type: 'MILESTONE', completed_at: '2026-01-02T00:00:00Z' })
    expect(buildCheckinUpdates([goal], { [goal.id]: false })).toEqual([
      { goal_id: goal.id, completed: false },
    ])
  })

  it('skips a milestone whose state has not changed', () => {
    const done = makeGoal({ tracking_type: 'MILESTONE', completed_at: '2026-01-02T00:00:00Z' })
    const notDone = makeGoal({ tracking_type: 'MILESTONE' })
    expect(buildCheckinUpdates([done, notDone], { [done.id]: true, [notDone.id]: false })).toEqual(
      [],
    )
  })

  it('skips blank and unchanged fields', () => {
    const numeric = makeGoal({ tracking_type: 'NUMERIC', current_value: 80, target_value: 120 })
    const prefilled = makeGoal({ tracking_type: 'NUMERIC', current_value: 84, target_value: 78 })
    const count = makeGoal({ tracking_type: 'COUNT', target_value: 50 })
    const manual = makeGoal({ tracking_type: 'MANUAL', manual_progress_percentage: 30 })
    const updates = buildCheckinUpdates([numeric, prefilled, count, manual], {
      [numeric.id]: '',
      [prefilled.id]: '84',
      [count.id]: '0',
      [manual.id]: '30',
    })
    expect(updates).toEqual([])
  })

  it('measures an unstarted numeric goal against its baseline', () => {
    const goal = makeGoal({
      tracking_type: 'NUMERIC',
      current_value: null,
      baseline_value: 80,
      target_value: 120,
    })
    expect(buildCheckinUpdates([goal], { [goal.id]: '80' })).toEqual([])
    expect(buildCheckinUpdates([goal], { [goal.id]: '90' })).toEqual([
      { goal_id: goal.id, numeric_value: 90 },
    ])
  })

  it('ignores values that are not numbers', () => {
    const goal = makeGoal({ tracking_type: 'NUMERIC', target_value: 120 })
    expect(buildCheckinUpdates([goal], { [goal.id]: 'heavy' })).toEqual([])
  })

  it('targets sub-goals instead of their parent, which the API rejects', () => {
    const child = makeGoal({ tracking_type: 'COUNT', target_value: 10, parent_goal_id: 'parent' })
    const parent = makeGoal({ id: 'parent', children: [child] })
    expect(checkinTargets([parent])).toEqual([child])
    expect(buildCheckinUpdates([parent], { [parent.id]: '5', [child.id]: '2' })).toEqual([
      { goal_id: child.id, numeric_delta: 2 },
    ])
  })

  it('trims the note and nulls it when empty', () => {
    const payload = buildCheckinPayload([], {}, { date: '2026-01-05', note: '   ' })
    expect(payload).toEqual({ date: '2026-01-05', note: null, updates: [] })
    expect(
      buildCheckinPayload([], {}, { date: '2026-01-05', note: '  Tough one  ' }).note,
    ).toBe('Tough one')
  })
})
