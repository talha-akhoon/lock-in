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

/** Place `stepId` among the other ids at `toIndex` (0 = first, length = last). */
export function insertIdAt(ids: string[], stepId: string, toIndex: number): string[] {
  const without = ids.filter((id) => id !== stepId)
  if (without.length === ids.length) return ids
  const clamped = Math.max(0, Math.min(without.length, toIndex))
  return [...without.slice(0, clamped), stepId, ...without.slice(clamped)]
}

export function dropIndexForY(
  rows: { id: string; top: number; bottom: number }[],
  draggedId: string,
  y: number,
): number {
  const others = rows.filter((row) => row.id !== draggedId)
  for (let index = 0; index < others.length; index += 1) {
    const row = others[index]
    if (row && y < (row.top + row.bottom) / 2) return index
  }
  return others.length
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
