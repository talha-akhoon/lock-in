import { describe, expect, it } from 'vitest'
import {
  defaultTrackingType,
  emptyGoalForm,
  goalFormSchema,
  toGoalInput,
  usesNumericFields,
  type GoalFormValues,
} from './goalSchema'

const base: GoalFormValues = {
  ...emptyGoalForm('PHYSICAL'),
  title: 'Deadlift 120kg',
  tracking_type: 'MILESTONE',
}

function parse(overrides: Partial<GoalFormValues>) {
  return goalFormSchema.safeParse({ ...base, ...overrides })
}

describe('goal form validation', () => {
  it('requires a title', () => {
    const result = parse({ title: '  ' })
    expect(result.success).toBe(false)
    expect(result.error?.issues[0].path).toEqual(['title'])
  })

  it('accepts a milestone with no numeric fields', () => {
    expect(parse({ tracking_type: 'MILESTONE' }).success).toBe(true)
  })

  it('rejects a numeric goal without a target', () => {
    const result = parse({ tracking_type: 'NUMERIC', target_value: '' })
    expect(result.success).toBe(false)
    expect(result.error?.issues[0].path).toEqual(['target_value'])
  })

  it('rejects a count goal whose target is not above zero', () => {
    expect(parse({ tracking_type: 'COUNT', target_value: '0' }).success).toBe(false)
    expect(parse({ tracking_type: 'COUNT', target_value: '30' }).success).toBe(true)
  })

  it('defaults physical goals to the current figure and religious ones to a daily amount', () => {
    expect(defaultTrackingType('PHYSICAL')).toBe('NUMERIC')
    expect(defaultTrackingType('RELIGIOUS')).toBe('COUNT')
    expect(defaultTrackingType('CAREER')).toBe('MILESTONE')
  })

  it('only shows numeric fields for the types that use them', () => {
    expect(usesNumericFields('NUMERIC')).toBe(true)
    expect(usesNumericFields('COUNT')).toBe(true)
    expect(usesNumericFields('MILESTONE')).toBe(false)
    expect(usesNumericFields('MANUAL')).toBe(false)
  })
})

describe('goal payload construction', () => {
  it('strips numeric fields from a milestone', () => {
    const values = goalFormSchema.parse({
      ...base,
      tracking_type: 'MILESTONE',
      baseline_value: '5',
      target_value: '10',
      unit: 'kg',
    })
    expect(toGoalInput(values)).toMatchObject({
      tracking_type: 'MILESTONE',
      baseline_value: null,
      target_value: null,
      current_value: null,
      unit: null,
      target_direction: null,
      manual_progress_percentage: null,
    })
  })

  it('gives a count goal a zero baseline when starting from scratch', () => {
    const values = goalFormSchema.parse({ ...base, tracking_type: 'COUNT', target_value: '100' })
    expect(toGoalInput(values)).toMatchObject({
      baseline_value: 0,
      current_value: 0,
      target_value: 100,
      target_direction: 'AT_LEAST',
    })
  })

  it('counts a running-total starting amount as progress from zero', () => {
    const values = goalFormSchema.parse({
      ...base,
      tracking_type: 'COUNT',
      baseline_value: '2',
      target_value: '12',
    })
    expect(toGoalInput(values)).toMatchObject({
      baseline_value: 0,
      current_value: 2,
      target_value: 12,
    })
  })

  it('starts a numeric goal at its baseline', () => {
    const values = goalFormSchema.parse({
      ...base,
      tracking_type: 'NUMERIC',
      baseline_value: '80',
      target_value: '120',
      target_direction: 'AT_LEAST',
      unit: 'kg',
    })
    expect(toGoalInput(values)).toMatchObject({
      baseline_value: 80,
      current_value: 80,
      target_value: 120,
      unit: 'kg',
    })
  })

  it('defaults a numeric baseline to zero when left blank', () => {
    const values = goalFormSchema.parse({
      ...base,
      tracking_type: 'NUMERIC',
      baseline_value: '',
      target_value: '120',
    })
    expect(toGoalInput(values).baseline_value).toBe(0)
  })

  it('starts a manual goal at zero percent when left blank', () => {
    const values = goalFormSchema.parse({ ...base, tracking_type: 'MANUAL' })
    expect(toGoalInput(values).manual_progress_percentage).toBe(0)
  })

  it('keeps a manual starting percentage', () => {
    const values = goalFormSchema.parse({
      ...base,
      tracking_type: 'MANUAL',
      manual_progress_percentage: '25',
    })
    expect(toGoalInput(values).manual_progress_percentage).toBe(25)
  })

  it('attaches a parent when creating a sub-goal', () => {
    const values = goalFormSchema.parse(base)
    expect(toGoalInput(values, 'parent-id').parent_goal_id).toBe('parent-id')
  })

  it('nulls an empty description rather than sending an empty string', () => {
    const values = goalFormSchema.parse({ ...base, description: '   ' })
    expect(toGoalInput(values).description).toBeNull()
  })
})
