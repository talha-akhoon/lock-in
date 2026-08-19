import { GripVertical, LockKeyhole, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Progress } from '../../components/primitives'
import { useReorderGoalSteps } from '../../hooks/queries'
import type { Goal } from '../../lib/types'
import { dropIndexForY, insertIdAt, movedStepIds } from './stepOrder'

const DRAG_THRESHOLD_PX = 5

export function GoalSteps({
  parent,
  canDelete,
  onDelete,
  linkTitles,
}: {
  parent: Goal
  canDelete?: boolean
  onDelete?: (goal: Goal) => void
  linkTitles?: boolean
}) {
  const reorder = useReorderGoalSteps()
  const steps = parent.children
  const canReorder = steps.length > 1
  const [dragId, setDragId] = useState<string | null>(null)
  const [previewIds, setPreviewIds] = useState<string[] | null>(null)
  const rowRefs = useRef(new Map<string, HTMLDivElement>())
  const stopDrag = useRef<(() => void) | null>(null)

  const orderedIds = previewIds ?? steps.map((step) => step.id)
  const visible = orderedIds.flatMap((id) => {
    const step = steps.find((child) => child.id === id)
    return step ? [step] : []
  })

  useEffect(() => () => stopDrag.current?.(), [])

  function persist(next: string[]) {
    const current = steps.map((step) => step.id)
    if (next.length === current.length && next.every((id, index) => id === current[index])) {
      return
    }
    if (reorder.isPending) return
    reorder.mutate({ parentId: parent.id, orderedIds: next })
  }

  function startDrag(event: React.PointerEvent<HTMLButtonElement>, stepId: string) {
    if (!canReorder || event.button !== 0 || reorder.isPending) return
    event.preventDefault()
    const pointerId = event.pointerId
    const originY = event.clientY
    let latest = orderedIds.slice()
    let active = false

    const onMove = (moveEvent: PointerEvent) => {
      if (moveEvent.pointerId !== pointerId) return
      if (!active && Math.abs(moveEvent.clientY - originY) < DRAG_THRESHOLD_PX) return
      active = true
      moveEvent.preventDefault()
      setDragId(stepId)
      const boxes = latest.flatMap((id) => {
        const node = rowRefs.current.get(id)
        if (!node) return []
        const rect = node.getBoundingClientRect()
        return [{ id, top: rect.top, bottom: rect.bottom }]
      })
      latest = insertIdAt(latest, stepId, dropIndexForY(boxes, stepId, moveEvent.clientY))
      setPreviewIds(latest)
    }

    const finish = (upEvent: PointerEvent) => {
      if (upEvent.pointerId !== pointerId) return
      cleanup()
      setDragId(null)
      setPreviewIds(null)
      if (active) persist(latest)
    }

    const cleanup = () => {
      stopDrag.current = null
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', finish)
      window.removeEventListener('pointercancel', finish)
    }

    stopDrag.current?.()
    stopDrag.current = cleanup
    window.addEventListener('pointermove', onMove, { passive: false })
    window.addEventListener('pointerup', finish)
    window.addEventListener('pointercancel', finish)
  }

  function onHandleKey(event: React.KeyboardEvent<HTMLButtonElement>, step: Goal) {
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
    event.preventDefault()
    const next = movedStepIds(
      visible.map((child) => child.id),
      step.id,
      event.key === 'ArrowUp' ? 'up' : 'down',
    )
    if (next) persist(next)
  }

  return (
    <>
      {visible.map((child) => (
        <div
          className={[
            'subgoal',
            canReorder ? 'reorderable' : '',
            dragId === child.id ? 'dragging' : '',
          ]
            .filter(Boolean)
            .join(' ')}
          key={child.id}
          ref={(node) => {
            if (node) rowRefs.current.set(child.id, node)
            else rowRefs.current.delete(child.id)
          }}
        >
          {canReorder && (
            <button
              type="button"
              className="subgoal-handle"
              aria-label={`Reorder ${child.title}`}
              aria-keyshortcuts="ArrowUp ArrowDown"
              aria-grabbed={dragId === child.id}
              disabled={reorder.isPending}
              onPointerDown={(event) => startDrag(event, child.id)}
              onKeyDown={(event) => onHandleKey(event, child)}
            >
              <GripVertical />
            </button>
          )}
          <span>
            {child.visibility === 'PRIVATE' && <LockKeyhole aria-label="Private step" />}{' '}
            {linkTitles ? <Link to={`/goals/${child.id}`}>{child.title}</Link> : child.title}
          </span>
          <Progress value={child.progress_percentage} tone="muted" />
          <b>{Math.round(child.progress_percentage)}%</b>
          {canDelete && onDelete && (
            <div className="subgoal-actions">
              <button
                type="button"
                className="icon-button tiny"
                onClick={() => onDelete(child)}
                aria-label={`Delete ${child.title}`}
              >
                <Trash2 />
              </button>
            </div>
          )}
        </div>
      ))}
    </>
  )
}
