import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { InfoTip } from '../../components/InfoTip'
import { Modal } from '../../components/Modal'
import { FieldError } from '../../components/primitives'
import { CATEGORY_META } from '../../lib/categories'
import { TRACKING_HELP, trackingExample } from '../../lib/help'
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
    baseline_value: trimDecimal(
      goal.tracking_type === 'COUNT' ? (goal.current_value ?? goal.baseline_value) : goal.baseline_value,
    ),
    target_value: trimDecimal(goal.target_value),
    manual_progress_percentage:
      goal.manual_progress_percentage == null ? '' : String(goal.manual_progress_percentage),
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
  lockedNotice,
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
  /** Adding while locked: the addition joins the lock and cannot be undone. */
  lockedNotice?: boolean
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
  const selectedCategory = watch('category')
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
        {lockedNotice && (
          <p className="locked-fact">
            Your commitment is locked, so this joins it immediately — you won’t be able to edit or
            remove it. A Required goal is scored for the forfeit.
          </p>
        )}
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

        <fieldset className="field tracking-choices" disabled={lockedFields}>
          <legend>
            How will you track this?
            <InfoTip label="What do these tracking options mean?" heading="Tracking method">
              <TrackingMethodHelp selected={trackingType} category={selectedCategory} />
            </InfoTip>
          </legend>
          {TRACKING_TYPES.map((item) => {
            const copy = TRACKING_HELP[item]
            return (
              <label key={item} className={item === trackingType ? 'current' : undefined}>
                <input type="radio" value={item} {...register('tracking_type')} />
                <span>
                  <b>{copy.title}</b>
                  <span>{copy.checkin}</span>
                  <em>e.g. {trackingExample(item, selectedCategory)}</em>
                </span>
              </label>
            )
          })}
        </fieldset>

        {showNumbers && (
          <>
            <div className="form-row">
              <label>
                Where you are now
                <input
                  {...register('baseline_value')}
                  type="number"
                  step="any"
                  disabled={lockedFields}
                  placeholder={trackingType === 'COUNT' ? '0 if you have not started' : '0'}
                />
                <FieldError message={errors.baseline_value?.message} />
              </label>
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
            <p className="hint">
              {trackingType === 'COUNT'
                ? 'What you already have counts toward the target.'
                : 'Progress is how far you move from here to the target.'}
            </p>
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

        {trackingType === 'MANUAL' && (
          <label>
            Where you are now
            <input
              {...register('manual_progress_percentage')}
              type="number"
              min={0}
              max={100}
              step={1}
              disabled={lockedFields}
              placeholder="0"
            />
            <FieldError message={errors.manual_progress_percentage?.message} />
            <span className="hint">A percentage from 0 to 100. Progress is measured from here.</span>
          </label>
        )}

        <div className="form-row checks">
          {lockedFields ? (
            /* A disabled tick renders grey in every browser, which makes a required
               goal look optional. Once locked, state this in words instead. */
            <p className="locked-fact">
              {goal?.required
                ? 'Required to avoid the forfeit'
                : 'Optional — no forfeit, and kept out of your percentage'}
            </p>
          ) : (
            <div>
              <label className="checkbox">
                <input type="checkbox" {...register('required')} /> Required to avoid the forfeit
              </label>
              <span className="hint">
                Untick for optional — no forfeit, and kept out of your percentage.
              </span>
            </div>
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
