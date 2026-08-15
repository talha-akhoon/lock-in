import { z } from 'zod'
import { CATEGORIES, TRACKING_TYPES, type GoalInput } from '../../lib/types'

/** Blank number inputs arrive as '' — treat them as absent rather than zero. */
const optionalNumber = z
  .union([z.string(), z.number()])
  .transform((value) => (value === '' || value === null ? null : Number(value)))
  .refine((value) => value === null || Number.isFinite(value), 'Enter a number')

export const goalFormSchema = z
  .object({
    category: z.enum(CATEGORIES),
    title: z.string().trim().min(1, 'Give the goal a title').max(255, 'Title is too long'),
    description: z.string().trim().max(2000, 'Description is too long').optional(),
    tracking_type: z.enum(TRACKING_TYPES),
    baseline_value: optionalNumber.optional(),
    target_value: optionalNumber.optional(),
    unit: z.string().trim().max(64, 'Unit is too long').optional(),
    target_direction: z.enum(['AT_LEAST', 'AT_MOST']),
    visibility: z.enum(['TEAM', 'PRIVATE']),
    required: z.boolean(),
  })
  .superRefine((value, ctx) => {
    if (value.tracking_type === 'NUMERIC' && value.target_value == null) {
      ctx.addIssue({
        code: 'custom',
        path: ['target_value'],
        message: 'Numeric goals need a target',
      })
    }
    if (value.tracking_type === 'COUNT' && !(Number(value.target_value) > 0)) {
      ctx.addIssue({
        code: 'custom',
        path: ['target_value'],
        message: 'Count goals need a target above zero',
      })
    }
  })

export type GoalFormValues = z.input<typeof goalFormSchema>
export type GoalFormParsed = z.output<typeof goalFormSchema>

export const emptyGoalForm = (category: GoalFormValues['category']): GoalFormValues => ({
  category,
  title: '',
  description: '',
  tracking_type: 'MILESTONE',
  baseline_value: '',
  target_value: '',
  unit: '',
  target_direction: 'AT_LEAST',
  visibility: 'TEAM',
  required: true,
})

/** Strips fields the tracking type does not use, matching backend normalisation. */
export function toGoalInput(
  values: GoalFormParsed,
  parentGoalId: string | null = null,
): GoalInput {
  const numeric = values.tracking_type === 'NUMERIC'
  const count = values.tracking_type === 'COUNT'
  const manual = values.tracking_type === 'MANUAL'
  const baseline = numeric ? (values.baseline_value ?? 0) : count ? 0 : null

  return {
    category: values.category,
    title: values.title.trim(),
    description: values.description?.trim() ? values.description.trim() : null,
    tracking_type: values.tracking_type,
    baseline_value: baseline,
    target_value: numeric || count ? (values.target_value ?? null) : null,
    current_value: baseline,
    unit: numeric || count ? (values.unit?.trim() || null) : null,
    target_direction: numeric ? values.target_direction : count ? 'AT_LEAST' : null,
    manual_progress_percentage: manual ? 0 : null,
    visibility: values.visibility,
    required: values.required,
    parent_goal_id: parentGoalId,
  }
}

export const usesNumericFields = (type: GoalFormValues['tracking_type']) =>
  type === 'NUMERIC' || type === 'COUNT'
