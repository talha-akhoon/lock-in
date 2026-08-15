import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { InfoTip } from '../../components/InfoTip'
import { Modal } from '../../components/Modal'
import { FieldError } from '../../components/primitives'
import { CATEGORY_META, TRACKING_LABELS } from '../../lib/categories'
import { TrackingMethodHelp } from './TrackingMethodHelp'
import { CATEGORIES, TRACKING_TYPES, type Category, type Goal, type GoalInput } from '../../lib/types'
import {
  emptyGoalForm,
  goalFormSchema,
  toGoalInput,
  usesNumericFields,
  type GoalFormParsed,
  type GoalFormValues,
} from './goalSchema'

function trimDecimal(value: string | null): string {
  if (value === null) return ''
  const numeric = Number(value)
  return Number.isFinite(numeric) ? String(numeric) : value
}

function valuesFromGoal(goal: Goal): GoalFormValues {
  return {
    category: goal.category,
    title: goal.title,
    description: goal.description ?? '',
    tracking_type: goal.tracking_type,
    // The API pads decimals to four places; a form field should show 120, not 120.0000.
    baseline_value: trimDecimal(goal.baseline_value),
    target_value: trimDecimal(goal.target_value),
    unit: goal.unit ?? '',
    target_direction: goal.target_direction ?? 'AT_LEAST',
    visibility: goal.visibility,
    required: goal.required,
  }
}

export function GoalForm({
  goal,
  parent,
  category,
  lockedFields,
  onSubmit,
  onClose,
  pending,
  error,
}: {
  /** Present when editing; absent when creating. */
  goal?: Goal
  /** Present when creating a sub-goal under an existing goal. */
  parent?: Goal
  category?: Category
  /** After commitment only visibility and ordering may change. */
  lockedFields?: boolean
  onSubmit: (input: GoalInput) => void
  onClose: () => void
  pending?: boolean
  error?: string | null
}) {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<GoalFormValues, unknown, GoalFormParsed>({
    resolver: zodResolver(goalFormSchema),
    defaultValues: goal
      ? valuesFromGoal(goal)
      : emptyGoalForm(parent?.category ?? category ?? 'RELIGIOUS'),
  })

  const trackingType = watch('tracking_type')
  const showNumbers = usesNumericFields(trackingType)
  const title = goal ? 'Edit goal' : parent ? `Add a step to “${parent.title}”` : 'Add a goal'

  return (
    <Modal eyebrow={goal ? 'Your commitment' : 'New commitment'} title={title} onClose={onClose}>
      <form
        onSubmit={handleSubmit((values) =>
          onSubmit(toGoalInput(values, parent?.id ?? goal?.parent_goal_id ?? null)),
        )}
        noValidate
      >
        <label>
          Category
          <select {...register('category')} disabled={lockedFields || Boolean(parent)}>
            {CATEGORIES.map((item) => (
              <option key={item} value={item}>
                {CATEGORY_META[item].label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Goal title
          <input
            {...register('title')}
            placeholder="e.g. Deadlift 120kg"
            disabled={lockedFields}
            aria-invalid={Boolean(errors.title)}
          />
          <FieldError message={errors.title?.message} />
        </label>

        <label>
          Description
          <textarea
            {...register('description')}
            placeholder="Why does this matter?"
            disabled={lockedFields}
          />
          <FieldError message={errors.description?.message} />
        </label>

        <div className="field">
          <InfoTip label="What do these tracking options mean?" heading="Tracking method">
            <TrackingMethodHelp selected={trackingType} />
          </InfoTip>
          <select
            id="goal-tracking"
            aria-label="Tracking method"
            {...register('tracking_type')}
            disabled={lockedFields}
          >
            {TRACKING_TYPES.map((item) => (
              <option key={item} value={item}>
                {TRACKING_LABELS[item]}
              </option>
            ))}
          </select>
        </div>

        {showNumbers && (
          <>
            <div className="form-row">
              {trackingType === 'NUMERIC' && (
                <label>
                  Starting value
                  <input
                    {...register('baseline_value')}
                    type="number"
                    step="any"
                    disabled={lockedFields}
                  />
                  <FieldError message={errors.baseline_value?.message} />
                </label>
              )}
              <label>
                Target value
                <input
                  {...register('target_value')}
                  type="number"
                  step="any"
                  disabled={lockedFields}
                  aria-invalid={Boolean(errors.target_value)}
                />
                <FieldError message={errors.target_value?.message} />
              </label>
            </div>
            <div className="form-row">
              <label>
                Unit
                <input
                  {...register('unit')}
                  placeholder={trackingType === 'COUNT' ? 'sessions, books…' : 'kg, £, hours…'}
                  disabled={lockedFields}
                />
                <FieldError message={errors.unit?.message} />
              </label>
              {trackingType === 'NUMERIC' && (
                <label>
                  Direction
                  <select {...register('target_direction')} disabled={lockedFields}>
                    <option value="AT_LEAST">Increase to the target</option>
                    <option value="AT_MOST">Decrease to the target</option>
                  </select>
                </label>
              )}
            </div>
          </>
        )}

        <div className="form-row checks">
          {lockedFields ? (
            /* A disabled tick renders grey in every browser, which makes a required
               goal look optional. Once locked, state this in words instead. */
            <p className="locked-fact">
              {goal?.required ? 'Required to avoid the forfeit' : 'Optional — no forfeit attached'}
            </p>
          ) : (
            <label className="checkbox">
              <input type="checkbox" {...register('required')} /> Required to avoid the forfeit
            </label>
          )}
          <label>
            Visibility
            <select {...register('visibility')}>
              <option value="TEAM">Visible to the team</option>
              <option value="PRIVATE">Private — counts, but stays unnamed</option>
            </select>
          </label>
        </div>

        {lockedFields && (
          <p className="hint">
            Your commitment is locked. Only visibility can change now.
          </p>
        )}
        {error && <p className="error">{error}</p>}

        <div className="modal-actions">
          <button type="button" className="ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={pending}>
            {pending ? 'Saving…' : goal ? 'Save changes' : 'Add goal'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
