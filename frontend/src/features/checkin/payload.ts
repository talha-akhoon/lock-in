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

/**
 * Turns form state into the update list, one shape per tracking type.
 *
 * Only genuine changes are sent. Numeric and manual fields are prefilled with
 * the goal's current figure so the member can see where they are, and a
 * milestone tick reflects its stored state, so submitting an untouched form
 * must record nothing — otherwise every day would log a no-op entry and inflate
 * the heatmap and activity feed.
 */
export function buildCheckinUpdates(goals: Goal[], state: CheckinFormState): CheckinUpdate[] {
  const updates: CheckinUpdate[] = []
  for (const goal of checkinTargets(goals)) {
    const raw = state[goal.id]
    if (raw === undefined || raw === null || raw === '') continue

    if (goal.tracking_type === 'MILESTONE') {
      const completed = raw === true || raw === 'on' || raw === 'true'
      if (completed === Boolean(goal.completed_at)) continue
      updates.push({ goal_id: goal.id, completed })
      continue
    }

    const value = Number(raw)
    if (!Number.isFinite(value)) continue

    if (goal.tracking_type === 'MANUAL') {
      const clamped = Math.max(0, Math.min(100, Math.round(value)))
      if (clamped === (goal.manual_progress_percentage ?? 0)) continue
      updates.push({ goal_id: goal.id, manual_percentage: clamped })
    } else if (goal.tracking_type === 'COUNT') {
      if (value === 0) continue
      updates.push({ goal_id: goal.id, numeric_delta: value })
    } else {
      // The stored figure is a decimal string, so compare as numbers.
      const stored = Number(goal.current_value ?? goal.baseline_value ?? NaN)
      if (Number.isFinite(stored) && value === stored) continue
      updates.push({ goal_id: goal.id, numeric_value: value })
    }
  }
  return updates
}

export function buildCheckinPayload(
  goals: Goal[],
  state: CheckinFormState,
  { date, note }: { date: string; note: string | null },
): CheckinPayload {
  return {
    date,
    note: note?.trim() ? note.trim() : null,
    updates: buildCheckinUpdates(goals, state),
  }
}
