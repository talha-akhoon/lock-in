import type { CheckinPayload, CheckinUpdate, Goal } from '../../lib/types'

/** Raw form state: goal id to the control's value. */
export type CheckinFormState = Record<string, string | boolean>

/**
 * Parent goals derive their progress from children, and the API rejects direct
 * updates to them, so only leaves are ever checked in against.
 */
export function checkinTargets(goals: Goal[]): Goal[] {
  return goals.flatMap((goal) => (goal.children.length ? goal.children : [goal]))
}

function isTicked(raw: string | boolean | undefined): boolean {
  return raw === true || raw === 'on' || raw === 'true'
}

function storedNumber(raw: string | boolean | undefined): number {
  return typeof raw === 'string' || typeof raw === 'number' ? Number(raw) : NaN
}

/**
 * Turns form state into the update list, one shape per tracking type.
 *
 * Only genuine changes are sent. Numeric and manual fields are prefilled with
 * the goal's current figure so the member can see where they are, and a
 * milestone tick reflects its stored state, so submitting an untouched form
 * must record nothing — otherwise every day would log a no-op entry and inflate
 * the heatmap and activity feed.
 *
 * `saved` is the form as last loaded or last successfully written. After a save
 * the day's query can still hold a stale `completed_at`, so the tick must be
 * compared with that snapshot — otherwise unchecking an accidental save looks
 * like "nothing changed" and is refused.
 */
export function buildCheckinUpdates(
  goals: Goal[],
  state: CheckinFormState,
  baseline = false,
  saved?: CheckinFormState,
): CheckinUpdate[] {
  const updates: CheckinUpdate[] = []
  for (const goal of checkinTargets(goals)) {
    const raw = state[goal.id]
    if (goal.tracking_type === 'MILESTONE') {
      // An unticked box is `false`, not empty — that is how a reopen is sent.
      if (raw === undefined || raw === null) continue
      const completed = isTicked(raw)
      const was = saved ? isTicked(saved[goal.id]) : Boolean(goal.completed_at)
      if (completed === was) continue
      updates.push({ goal_id: goal.id, completed })
      continue
    }

    if (raw === undefined || raw === null || raw === '') continue

    const value = Number(raw)
    if (!Number.isFinite(value)) continue

    if (goal.tracking_type === 'MANUAL') {
      const clamped = Math.max(0, Math.min(100, Math.round(value)))
      const previous = saved
        ? Math.max(0, Math.min(100, Math.round(storedNumber(saved[goal.id]) || 0)))
        : (goal.manual_progress_percentage ?? 0)
      if (clamped === previous) continue
      updates.push({ goal_id: goal.id, manual_percentage: clamped })
    } else if (goal.tracking_type === 'COUNT' && !baseline) {
      if (value === 0) continue
      if (saved && storedNumber(saved[goal.id]) === value) continue
      updates.push({ goal_id: goal.id, numeric_delta: value })
    } else {
      // Starting point and numeric check-ins set the current figure. Count
      // goals only do this before kick-off; during the challenge they add.
      const stored = saved
        ? storedNumber(saved[goal.id])
        : Number(goal.current_value ?? goal.baseline_value ?? NaN)
      if (Number.isFinite(stored) && value === stored) continue
      updates.push({ goal_id: goal.id, numeric_value: value })
    }
  }
  return updates
}

export function buildCheckinPayload(
  goals: Goal[],
  state: CheckinFormState,
  {
    date,
    note,
    baseline = false,
    saved,
  }: { date: string; note: string | null; baseline?: boolean; saved?: CheckinFormState },
): CheckinPayload {
  return {
    date,
    note: note?.trim() ? note.trim() : null,
    updates: buildCheckinUpdates(goals, state, baseline, saved),
  }
}

/**
 * Count fields are today's amount, not a running figure. After a save they go
 * back to blank so a second submit does not add the same delta again.
 */
export function formStateAfterSave(
  state: CheckinFormState,
  goals: Goal[],
  baseline = false,
): CheckinFormState {
  const next = { ...state }
  if (baseline) return next
  for (const goal of checkinTargets(goals)) {
    if (goal.tracking_type === 'COUNT') next[goal.id] = ''
  }
  return next
}

/** Apply a saved payload onto the day's cached goals so the form's baseline moves. */
export function applyCheckinUpdates(goals: Goal[], updates: CheckinUpdate[]): Goal[] {
  const byId = new Map(updates.map((update) => [update.goal_id, update]))

  const apply = (goal: Goal): Goal => {
    const children = goal.children.map(apply)
    const update = byId.get(goal.id)
    const childrenChanged = children.some((child, index) => child !== goal.children[index])
    if (!update && !childrenChanged) return goal

    const next: Goal = { ...goal, children }
    if (!update) return next
    if (update.completed === true) {
      next.completed_at = next.completed_at ?? new Date().toISOString()
      next.progress_percentage = 100
    } else if (update.completed === false) {
      next.completed_at = null
      next.progress_percentage = 0
    }
    if (update.manual_percentage !== undefined) {
      next.manual_progress_percentage = update.manual_percentage
      next.progress_percentage = update.manual_percentage
    }
    if (update.numeric_value !== undefined) {
      next.current_value = String(update.numeric_value)
    }
    if (update.numeric_delta !== undefined) {
      next.current_value = String(Number(next.current_value ?? 0) + update.numeric_delta)
    }
    return next
  }

  return goals.map(apply)
}
