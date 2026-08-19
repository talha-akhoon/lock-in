import type { Goal } from '../../lib/types'

export type StepDirection = 'up' | 'down'

export function movedStepIds(
  ids: string[],
  stepId: string,
  direction: StepDirection,
): string[] | null {
  const index = ids.indexOf(stepId)
  const swapWith = direction === 'up' ? index - 1 : index + 1
  if (index < 0 || swapWith < 0 || swapWith >= ids.length) return null
  const next = [...ids]
  const current = next[index]
  const neighbour = next[swapWith]
  if (current === undefined || neighbour === undefined) return null
  next[index] = neighbour
  next[swapWith] = current
  return next
}

export function orderedChildren(goal: Goal, orderedIds: string[]): Goal {
  const byId = new Map(goal.children.map((child) => [child.id, child]))
  return {
    ...goal,
    children: orderedIds.flatMap((id) => {
      const child = byId.get(id)
      return child ? [child] : []
    }),
  }
}
